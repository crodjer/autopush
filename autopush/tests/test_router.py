# -*- coding: utf-8 -*-
from unittest import TestCase
import uuid

from mock import Mock, PropertyMock
from moto import mock_dynamodb2
from nose.tools import eq_, ok_
from twisted.trial import unittest
from twisted.internet.error import ConnectError

import apns
import gcmclient

from autopush.db import (
    Router,
    Storage,
    ProvisionedThroughputExceededException,
    ItemNotFound,
)
from autopush.endpoint import Notification
from autopush.router import APNSRouter, GCMRouter, SimpleRouter
from autopush.router.interface import RouterException, RouterResponse, IRouter
from autopush.settings import AutopushSettings


mock_dynamodb2 = mock_dynamodb2()


def setUp():
    mock_dynamodb2.start()


def tearDown():
    mock_dynamodb2.stop()


class MockAssist(object):
    def __init__(self, results):
        self.cur = 0
        self.max = len(results)
        self.results = results

    def __call__(self, *args, **kwargs):
        try:
            r = self.results[self.cur]
            print r
            if callable(r):
                return r()
            else:
                return r
        finally:
            if self.cur < (self.max-1):
                self.cur += 1


class RouterInterfaceTestCase(TestCase):
    def test_not_implemented(self):
        self.assertRaises(NotImplementedError, IRouter, None, None)

        def init(self, settings, router_conf):
            pass
        IRouter.__init__ = init
        ir = IRouter(None, None)
        self.assertRaises(NotImplementedError, ir.register, "uaid", {})
        self.assertRaises(NotImplementedError, ir.route_notification, "uaid",
                          {})


dummy_chid = str(uuid.uuid4())
dummy_uaid = str(uuid.uuid4())


class APNSRouterTestCase(unittest.TestCase):
    def setUp(self):
        settings = AutopushSettings(
            hostname="localhost",
            statsd_host=None,
        )
        apns_config = {'cert_file': 'fake.cert', 'key_file': 'fake.key'}
        self.mock_apns = Mock(spec=apns.APNs)
        self.router = APNSRouter(settings, apns_config)
        self.router.apns = self.mock_apns
        self.notif = Notification(10, "data", dummy_chid)
        self.router_data = dict(router_data=dict(token="connect_data"))

    def test_register(self):
        result = self.router.register("uaid", {"token": "connect_data"})
        eq_(result, {"token": "connect_data"})

    def test_register_bad(self):
        self.assertRaises(RouterException, self.router.register, "uaid", {})

    def test_route_notification(self):
        d = self.router.route_notification(self.notif, self.router_data)

        def check_results(result):
            ok_(isinstance(result, RouterResponse))
            self.mock_apns.gateway_server.send_notification.assert_called()

        d.addCallback(check_results)
        return d

    def test_message_pruning(self):
        self.router.messages = {1: {'token': 'dump', 'payload': {}}}
        d = self.router.route_notification(self.notif, self.router_data)

        def check_results(result):
            ok_(isinstance(result, RouterResponse))
            self.mock_apns.gateway_server.send_notification.assert_called()
            eq_(len(self.router.messages), 1)
        d.addCallback(check_results)
        return d

    def test_response_listener_with_success(self):
        self.router.messages = {1: {'token': 'dump', 'payload': {}}}
        self.router._error(dict(status=0, identifier=1))
        eq_(len(self.router.messages), 0)

    def test_response_listener_with_nonretryable_error(self):
        self.router.messages = {1: {'token': 'dump', 'payload': {}}}
        self.router._error(dict(status=2, identifier=1))
        eq_(len(self.router.messages), 1)

    def test_response_listener_with_retryable_existing_message(self):
        self.router.messages = {1: {'token': 'dump', 'payload': {}}}
        # Mock out the _connect call to be harmless
        self.router._connect = Mock()
        self.router._error(dict(status=1, identifier=1))
        eq_(len(self.router.messages), 1)
        self.router.apns.gateway_server.send_notification.assert_called()

    def test_response_listener_with_retryable_non_existing_message(self):
        self.router.messages = {1: {'token': 'dump', 'payload': {}}}
        self.router._error(dict(status=1, identifier=10))
        eq_(len(self.router.messages), 1)


class GCMRouterTestCase(unittest.TestCase):
    def setUp(self):
        settings = AutopushSettings(
            hostname="localhost",
            statsd_host=None,
        )
        # Mock out GCM client
        self._old_gcm = gcmclient.GCM
        gcmclient.GCM = Mock(spec=gcmclient.GCM)

        gcm_config = {'apikey': '12345678abcdefg'}
        self.router = GCMRouter(settings, gcm_config)
        self.notif = Notification(10, "data", dummy_chid)
        self.router_data = dict(router_data=dict(token="connect_data"))
        mock_result = Mock(spec=gcmclient.gcm.Result)
        mock_result.canonical = dict()
        mock_result.failed = dict()
        mock_result.not_registered = dict()
        mock_result.needs_retry.return_value = False
        self.mock_result = mock_result
        self.router.gcm.send.return_value = mock_result

    def tearDown(self):
        gcmclient.GCM = self._old_gcm

    def _check_error_call(self, exc, code):
        ok_(isinstance(exc, RouterException))
        eq_(exc.status_code, code)
        self.router.gcm.send.assert_called()
        self.flushLoggedErrors()

    def test_register(self):
        result = self.router.register("uaid", {"token": "connect_data"})
        eq_(result, {"token": "connect_data"})

    def test_register_bad(self):
        self.assertRaises(RouterException, self.router.register, "uaid", {})

    def test_router_notification(self):
        d = self.router.route_notification(self.notif, self.router_data)

        def check_results(result):
            ok_(isinstance(result, RouterResponse))
            self.router.gcm.send.assert_called()
        d.addCallback(check_results)
        return d

    def test_router_notification_gcm_auth_error(self):
        def throw_auth(arg):
            raise gcmclient.GCMAuthenticationError()
        self.router.gcm.send.side_effect = throw_auth
        d = self.router.route_notification(self.notif, self.router_data)

        def check_results(fail):
            self._check_error_call(fail.value, 500)
        d.addBoth(check_results)
        return d

    def test_router_notification_gcm_other_error(self):
        def throw_other(arg):
            raise Exception("oh my!")
        self.router.gcm.send.side_effect = throw_other
        d = self.router.route_notification(self.notif, self.router_data)

        def check_results(fail):
            self._check_error_call(fail.value, 500)
        d.addBoth(check_results)
        return d

    def test_router_notification_gcm_id_change(self):
        self.mock_result.canonical["old"] = "new"
        d = self.router.route_notification(self.notif, self.router_data)

        def check_results(result):
            ok_(isinstance(result, RouterResponse))
            eq_(result.router_data, dict(token="new"))
            self.router.gcm.send.assert_called()
        d.addCallback(check_results)
        return d

    def test_router_notification_gcm_not_regged(self):
        self.mock_result.not_registered = {"connect_data": True}
        d = self.router.route_notification(self.notif, self.router_data)

        def check_results(result):
            ok_(isinstance(result, RouterResponse))
            eq_(result.router_data, dict())
            self.router.gcm.send.assert_called()
        d.addCallback(check_results)
        return d

    def test_router_notification_gcm_failed_items(self):
        self.mock_result.failed = dict(connect_data=True)
        d = self.router.route_notification(self.notif, self.router_data)

        def check_results(fail):
            self._check_error_call(fail.value, 503)
        d.addBoth(check_results)
        return d

    def test_router_notification_gcm_needs_retry(self):
        self.mock_result.needs_retry.return_value = True
        d = self.router.route_notification(self.notif, self.router_data)

        def check_results(fail):
            self._check_error_call(fail.value, 503)
        d.addBoth(check_results)
        return d


class SimplePushRouterTestCase(unittest.TestCase):
    def setUp(self):
        settings = AutopushSettings(
            hostname="localhost",
            statsd_host=None,
        )

        self.router = SimpleRouter(settings, {})
        self.notif = Notification(10, "data", dummy_chid)
        mock_result = Mock(spec=gcmclient.gcm.Result)
        mock_result.canonical = dict()
        mock_result.failed = dict()
        mock_result.not_registered = dict()
        mock_result.needs_retry.return_value = False
        self.router_mock = settings.router = Mock(spec=Router)
        self.storage_mock = settings.storage = Mock(spec=Storage)
        self.agent_mock = Mock(spec=settings.agent)
        settings.agent = self.agent_mock
        self.router.metrics = Mock()

    def _raise_connect_error(self):
        raise ConnectError()

    def _raise_db_error(self):
        raise ProvisionedThroughputExceededException(None, None)

    def _raise_item_error(self):
        raise ItemNotFound()

    def test_register(self):
        r = self.router.register(None, {})
        eq_(r, {})

    def test_route_to_connected(self):
        self.agent_mock.request.return_value = response_mock = Mock()
        response_mock.code = 200
        router_data = dict(node_id="http://somewhere", uaid=dummy_uaid)
        d = self.router.route_notification(self.notif, router_data)

        def verify_deliver(result):
            ok_(result, RouterResponse)
            eq_(result.status_code, 200)
        d.addBoth(verify_deliver)
        return d

    def test_route_connect_error(self):
        self.agent_mock.request.side_effect = MockAssist(
            [self._raise_connect_error])
        router_data = dict(node_id="http://somewhere", uaid=dummy_uaid)
        self.router_mock.clear_node.return_value = None
        d = self.router.route_notification(self.notif, router_data)

        def verify_deliver(fail):
            exc = fail.value
            ok_(exc, RouterException)
            eq_(exc.status_code, 503)
            self.flushLoggedErrors()
        d.addBoth(verify_deliver)
        return d

    def test_route_to_busy_node_save_old_version(self):
        self.agent_mock.request.return_value = response_mock = Mock()
        response_mock.code = 202
        self.storage_mock.save_notification.return_value = False
        router_data = dict(node_id="http://somewhere", uaid=dummy_uaid)
        d = self.router.route_notification(self.notif, router_data)

        def verify_deliver(result):
            ok_(result, RouterResponse)
            eq_(result.status_code, 202)
        d.addBoth(verify_deliver)
        return d

    def test_route_to_busy_node_save_throws_db_error(self):
        self.agent_mock.request.return_value = response_mock = Mock()
        response_mock.code = 202
        self.storage_mock.save_notification.side_effect = MockAssist(
            [self._raise_db_error]
        )
        router_data = dict(node_id="http://somewhere", uaid=dummy_uaid)
        d = self.router.route_notification(self.notif, router_data)

        def verify_deliver(fail):
            exc = fail.value
            ok_(exc, RouterException)
            eq_(exc.status_code, 503)
        d.addBoth(verify_deliver)
        return d

    def test_route_with_no_node_saves_and_lookup_fails(self):
        self.storage_mock.save_notification.return_value = True
        self.router_mock.get_uaid.side_effect = MockAssist(
            [self._raise_db_error]
        )
        router_data = dict(uaid=dummy_uaid)
        d = self.router.route_notification(self.notif, router_data)

        def verify_deliver(result):
            ok_(result, RouterResponse)
            eq_(result.status_code, 202)
        d.addBoth(verify_deliver)
        return d

    def test_route_with_no_node_saves_and_lookup_fails_with_item_error(self):
        self.storage_mock.save_notification.return_value = True
        self.router_mock.get_uaid.side_effect = MockAssist(
            [self._raise_item_error]
        )
        router_data = dict(uaid=dummy_uaid)
        d = self.router.route_notification(self.notif, router_data)

        def verify_deliver(fail):
            exc = fail.value
            ok_(exc, RouterException)
            eq_(exc.status_code, 404)
        d.addBoth(verify_deliver)
        return d

    def test_route_to_busy_node_saves_looks_up_and_no_node(self):
        self.agent_mock.request.return_value = response_mock = Mock()
        response_mock.code = 202
        self.storage_mock.save_notification.return_value = True
        self.router_mock.get_uaid.return_value = dict()
        router_data = dict(node_id="http://somewhere", uaid=dummy_uaid)
        d = self.router.route_notification(self.notif, router_data)

        def verify_deliver(result):
            ok_(result, RouterResponse)
            eq_(result.status_code, 202)
        d.addBoth(verify_deliver)
        return d

    def test_route_to_busy_node_saves_looks_up_and_sends_check_202(self):
        self.agent_mock.request.return_value = response_mock = Mock()
        response_mock.code = 202
        self.storage_mock.save_notification.return_value = True
        router_data = dict(node_id="http://somewhere", uaid=dummy_uaid)
        self.router_mock.get_uaid.return_value = router_data

        d = self.router.route_notification(self.notif, router_data)

        def verify_deliver(result):
            ok_(result, RouterResponse)
            eq_(result.status_code, 202)
            self.router_mock.get_uaid.assert_called()
        d.addBoth(verify_deliver)
        return d

    def test_route_to_busy_node_saves_looks_up_and_send_check_fails(self):
        import autopush.router.simple as simple
        response_mock = Mock()
        self.agent_mock.request.side_effect = MockAssist(
            [response_mock, self._raise_connect_error])
        response_mock.code = 202
        self.storage_mock.save_notification.return_value = True
        router_data = dict(node_id="http://somewhere", uaid=dummy_uaid)
        self.router_mock.get_uaid.return_value = router_data

        d = self.router.route_notification(self.notif, router_data)

        def verify_deliver(result):
            ok_(result, RouterResponse)
            eq_(result.status_code, 202)
            self.router_mock.clear_node.assert_called()
            nk = simple.node_key(router_data["node_id"])
            eq_(simple.dead_cache.get(nk), True)
        d.addBoth(verify_deliver)
        return d

    def test_route_busy_node_saves_looks_up_and_send_check_fails_and_db(self):
        import autopush.router.simple as simple
        response_mock = Mock()
        self.agent_mock.request.side_effect = MockAssist(
            [response_mock, self._raise_connect_error])
        response_mock.code = 202
        self.storage_mock.save_notification.return_value = True
        router_data = dict(node_id="http://somewhere", uaid=dummy_uaid)
        self.router_mock.get_uaid.return_value = router_data
        self.router_mock.clear_node.side_effect = MockAssist(
            [self._raise_db_error]
        )

        d = self.router.route_notification(self.notif, router_data)

        def verify_deliver(result):
            ok_(result, RouterResponse)
            eq_(result.status_code, 202)
            self.router_mock.clear_node.assert_called()
            nk = simple.node_key(router_data["node_id"])
            eq_(simple.dead_cache.get(nk), True)
        d.addBoth(verify_deliver)
        return d

    def test_route_to_busy_node_saves_looks_up_and_sends_check_200(self):
        self.agent_mock.request.return_value = response_mock = Mock()
        response_mock.addCallback.return_value = response_mock
        type(response_mock).code = PropertyMock(
            side_effect=MockAssist([202, 200]))
        self.storage_mock.save_notification.return_value = True
        router_data = dict(node_id="http://somewhere", uaid=dummy_uaid)
        self.router_mock.get_uaid.return_value = router_data

        d = self.router.route_notification(self.notif, router_data)

        def verify_deliver(result):
            ok_(result, RouterResponse)
            eq_(result.status_code, 200)
            self.router.metrics.increment.assert_called_with(
                "router.broadcast.save_hit"
            )
        d.addBoth(verify_deliver)
        return d
