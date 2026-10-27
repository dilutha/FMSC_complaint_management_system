# FMSC Cases — Flutter client (Member A case module)

The case screens are My cases, Submit, Confirmation, Case detail and timeline, Attachment viewer, Confirm resolution and Reopen. They call the Django API at `API_BASE_URL`.

```bash
flutter pub get
flutter test
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000/api/v1/
```

- `lib/design/`: USJ design tokens and shared widgets (see `../docs/DESIGN_SYSTEM.md`)
- `lib/features/cases/`: data layer (`ApiCaseRepository`), screens, and `CaseRoutes` and `CaseScope` for integration
- `lib/integration/`: the `AuthSession` contract plus the placeholder sign-in. Member B replaces the placeholder.

For local development over plain HTTP on Android, allow cleartext traffic in a debug-only manifest or network-security config. Production builds must use HTTPS.
