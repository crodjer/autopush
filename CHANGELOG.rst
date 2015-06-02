==================
Autopush Changelog
==================

1.2.3 (**dev**)
===============

Features
--------

* Add debugging entry point for live interaction with autopush server.

1.2.2 (May 27, 2015)
====================

Features
--------

* Add additional metrics for writers/readers to indicate what twisted is still
  tracking connection-wise.

Bug Fixes
---------
* Correct trap for TCP connection closer

1.2.1 (May 20, 2015)
====================

Bug Fixes
---------
* Fix error with blank UAIDs being rejected as "already registered"

1.2.0 (May 19, 2015)
====================

Features
--------

* Pong delay can no longer be set, and uses an adaptive value based on the last
  ping to try and accurately compensate for higher latency connections. This
  also removes the min_ping_interval option such that if a client is pinging
  too frequently we will instead leave space for up to the clients timeout of
  10-sec (a hardcoded client value).

Bug Fixes
---------

* Fix 500 errors in endpoint caused by timeouts when trying to deliver to
  expired nodes in the cluster. Resolves Issue #75.
* Add CancelledError trap to all deferreds in websocket.py. Resolves Issue #74.
* Aggressively delete old TCP connections on device reregistration (#72)

Backwards Incompatibility
-------------------------

* Removed min_ping_interval config option.
* Removed pong_delay config option.

1.1rc2 (May 15, 2015)
=====================

Features
--------

* Add structured logging output for the endpoint for additional request
  metadata. Resolves Issue #67.

Bug Fixes
---------

* Fix bug with deferreds not being tracked, causing access to objects that were
  cleaned up. Resolves Issue #66.
* kill older, duplicate UAID entries that may still be connected.
* use Websocket Pings to detect dead connections.

1.0rc1 (Apr 29, 2015)
=====================

Features
--------

* Verify ability to read/write DynamoDB tables on startup. Resolves Issue #46.
* Send un-acknolwedged direct delivery messages to the router if the client is
  disconnected without ack'ing them. Resolves Issue #36.
* Use IProducer to more precisely monitor when the client has drained the data
  to immediately resume sending more data. Resolves Issue #28.
* Add /status HTTP endpoint for autopush/autoendpoint. Resolves Issue #27.
* Add example stage/prod config files. Resolves Issue #22.
* Switch internal routing from requests to twisted http-client. Resolves Issue
  #21.
* Add logging for user-agent to metrics tags. Resolves Issue #20.
* Add Datadog stats output. Resolves Issue #17.
* Add GCM and APNS Bridges. Resolves Issue #16.
* Use eliot structured logging for stdout logging that matches ops standard
  for logging. Resolves Issue #11.
* Allow storage/router table names to be configurable. Resolves Issue #4.
* Added optional CORS headers (use --cors to enable). Resolves Issue #3.
* Add provisioned error metrics to track when throughput is exceeded in AWS
  DynamoDB. Resolves Issue #2.
* Add Sentry support (SENTRY_DSN must be set in the environment). Resolves
  Issue #1.

Bug Fixes
---------

* Capture and log exceptions in websocket protocol functions.
* Fix bug with 'settings' in cyclone overriding cyclone's settings. Resolves
  Issue #13.
