# Platform API fixtures

These files are responses captured from the real Django backend (`/api/v1/…`). The data is synthetic and was created inside a database transaction that was then rolled back. `platform_contract_test.dart` checks that the Flutter models parse them, so a change to the API shape fails the Flutter tests.

The token in `login.json` has been replaced with a placeholder.

To regenerate them, create the same synthetic flow (one complaint and one suggestion; the suggestion accepted and given a 40 % progress update) and save each response unchanged. See the commit that added this folder.
