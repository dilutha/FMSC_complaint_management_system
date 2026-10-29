# FMSC Cases — Flutter client (Member A case module)

The case screens are My cases, Submit, Confirmation, Case detail and timeline, Attachment viewer, Confirm resolution and Reopen. They call the Django API at `API_BASE_URL`.

```bash
flutter pub get
flutter test
# Start the backend first (from backend/): python manage.py runserver
flutter run -d chrome          # web: uses http://127.0.0.1:8000/api/v1/
flutter run -d emulator-5554   # Android emulator: uses http://10.0.2.2:8000/api/v1/
# Physical phone on the same Wi-Fi: run `python manage.py runserver 0.0.0.0:8000`, add your
# computer's IP to DJANGO_ALLOWED_HOSTS, then:
flutter run --dart-define=API_BASE_URL=http://<your-computer-ip>:8000/api/v1/
```

- `lib/design/`: USJ design tokens and shared widgets (see `../docs/DESIGN_SYSTEM.md`)
- `lib/features/cases/`: data layer (`ApiCaseRepository`), screens, and `CaseRoutes` and `CaseScope` for integration
- `lib/integration/`: the `AuthSession` contract (implemented by `features/auth/data/platform_auth_session.dart`)

"No connection to the server" on the sign-in screen means the app could not reach Django at all. Check:
- that `runserver` is running;
- that the address suits the device. `10.0.2.2` works only inside the Android emulator; Chrome and desktop use `127.0.0.1`.

For local development over plain HTTP on Android, allow cleartext traffic in a debug-only manifest or network-security config. Production builds must use HTTPS.
