import 'package:flutter/material.dart';

import '../../../app/config.dart';
import '../../../core/api_client.dart';
import '../../../design/theme.dart';
import '../../../design/usj_colors.dart';
import '../../../design/widgets.dart';
import '../../../platform/platform_scope.dart';

/// Sign-in with university username or email. Replaces the case module's
/// placeholder sign-in screen (shared contract: AuthSession).
class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key, this.serverLabel, this.initialUsername = '', this.initialPassword = ''});

  /// Pre-filled from the home page's demo-account list (development demos only).
  final String initialUsername;
  final String initialPassword;

  /// Server address shown in connection errors; defaults to [AppConfig.serverLabel].
  final String? serverLabel;

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  late final _username = TextEditingController(text: widget.initialUsername);
  late final _password = TextEditingController(text: widget.initialPassword);
  bool _busy = false;
  bool _obscure = true;
  String? _error;
  bool _noticeRead = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_noticeRead) {
      _noticeRead = true;
      _error = PlatformScope.of(context).session.takeNotice();
    }
  }

  @override
  void dispose() {
    _username.dispose();
    _password.dispose();
    super.dispose();
  }

  /// The server address shown in connection errors (overridable in tests).
  String get _server => widget.serverLabel ?? AppConfig.serverLabel;

  /// Maps a failed sign-in to a message that tells the user what to do.
  String _messageFor(ApiException e) => switch (e) {
    ApiException(statusCode: 400) => 'Incorrect username or password. Check both and try again.',
    ApiException(statusCode: 429) => 'Too many sign-in attempts. Please wait a while and try again.',
    ApiException(code: 'timeout') =>
      'The server at $_server did not respond in time. Check that the backend is running and that '
          'this is the right address, then try again.',
    ApiException(isNetwork: true) =>
      'Cannot reach the server at $_server. Check that the backend is running and your internet '
          'connection, then try again.',
    ApiException(statusCode: >= 500) => 'The server had a problem signing you in. Please try again shortly.',
    _ => e.message,
  };

  Future<void> _signIn() async {
    if (_busy) return; // one request at a time (double taps, Enter key)
    if (!_formKey.currentState!.validate()) return;
    final scope = PlatformScope.of(context);
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final result = await scope.auth.signIn(_username.text.trim(), _password.text);
      _password.clear();
      await scope.session.signIn(token: result.token, user: result.user);
      // Opened from the public home page: close the sign-in route so the
      // role-specific dashboard underneath is shown.
      if (mounted && Navigator.of(context).canPop()) Navigator.of(context).popUntil((r) => r.isFirst);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = _messageFor(e));
    } catch (e, stack) {
      // Anything unexpected (e.g. a malformed response) must not leave the button stuck.
      debugPrint('Sign-in failed unexpectedly: $e\n$stack');
      if (mounted) setState(() => _error = 'Something went wrong while signing in. Please try again.');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: Navigator.of(context).canPop()
          ? AppBar(
              title: const Text('Sign in'),
              backgroundColor: UsjColors.surface,
              foregroundColor: UsjColors.maroon,
            )
          : null,
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(Space.xl),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Form(
                key: _formKey,
                child: AutofillGroup(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      const Center(child: UsjLogo(size: 96)),
                      const SizedBox(height: Space.lg),
                      Semantics(
                        header: true,
                        child: Text(
                          'FMSC Complaint & Suggestion Management',
                          textAlign: TextAlign.center,
                          style: theme.textTheme.titleLarge,
                        ),
                      ),
                      const SizedBox(height: Space.xs),
                      Text(
                        'Faculty of Management Studies and Commerce\nUniversity of Sri Jayewardenepura',
                        textAlign: TextAlign.center,
                        style: theme.textTheme.bodyMedium?.copyWith(color: UsjColors.textSecondary),
                      ),
                      const SizedBox(height: Space.xl),
                      if (_error != null) ...[
                        Semantics(
                          liveRegion: true,
                          child: Container(
                            padding: const EdgeInsets.all(Space.md),
                            decoration: BoxDecoration(
                              color: UsjColors.errorBg,
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Row(
                              children: [
                                const Icon(Icons.error_outline, color: UsjColors.error),
                                const SizedBox(width: Space.sm),
                                Expanded(child: Text(_error!, style: const TextStyle(color: UsjColors.error))),
                              ],
                            ),
                          ),
                        ),
                        const SizedBox(height: Space.lg),
                      ],
                      TextFormField(
                        controller: _username,
                        enabled: !_busy,
                        autofillHints: const [AutofillHints.username, AutofillHints.email],
                        keyboardType: TextInputType.emailAddress,
                        autocorrect: false,
                        textInputAction: TextInputAction.next,
                        decoration: const InputDecoration(
                          labelText: 'Username or university email',
                          prefixIcon: Icon(Icons.person_outline),
                        ),
                        validator: (v) => (v == null || v.trim().isEmpty) ? 'Enter your username or email.' : null,
                      ),
                      const SizedBox(height: Space.md),
                      TextFormField(
                        controller: _password,
                        enabled: !_busy,
                        obscureText: _obscure,
                        autofillHints: const [AutofillHints.password],
                        onFieldSubmitted: (_) => _signIn(),
                        decoration: InputDecoration(
                          labelText: 'Password',
                          prefixIcon: const Icon(Icons.lock_outline),
                          suffixIcon: IconButton(
                            tooltip: _obscure ? 'Show password' : 'Hide password',
                            icon: Icon(_obscure ? Icons.visibility_outlined : Icons.visibility_off_outlined),
                            onPressed: () => setState(() => _obscure = !_obscure),
                          ),
                        ),
                        validator: (v) => (v == null || v.isEmpty) ? 'Enter your password.' : null,
                      ),
                      const SizedBox(height: Space.xl),
                      FilledButton(
                        onPressed: _busy ? null : _signIn,
                        child: _busy
                            ? const Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  SizedBox.square(
                                    dimension: 18,
                                    child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                                  ),
                                  SizedBox(width: Space.sm),
                                  Text('Signing in…'),
                                ],
                              )
                            : const Text('Sign in'),
                      ),
                      const SizedBox(height: Space.lg),
                      Text(
                        'Forgot your password? Contact the faculty system administrator to reset it.',
                        textAlign: TextAlign.center,
                        style: theme.textTheme.bodySmall?.copyWith(color: UsjColors.textSecondary),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
