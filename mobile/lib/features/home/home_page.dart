import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../app/config.dart';

import '../../design/theme.dart';
import '../../design/tokens.dart';
import '../../design/usj_colors.dart';
import '../../design/widgets.dart';
import 'demo_accounts.dart';

/// Public landing page (no sign-in needed). Colours come only from the official
/// USJ palette (docs/DESIGN_SYSTEM.md) on neutral backgrounds; light tints are
/// those same colours at low opacity. Content describes what the app actually
/// does: no statistics, testimonials, guarantees or invented contact details.
class HomePage extends StatefulWidget {
  const HomePage({
    super.key,
    required this.onLogin,
    this.onDashboard,
    this.onDemoLogin,
    this.showDemoAccounts = AppConfig.showDemoAccounts,
  });

  /// Opens the existing sign-in screen.
  final VoidCallback onLogin;

  /// Opens sign-in pre-filled with a demo account; falls back to [onLogin].
  final void Function(String username, String password)? onDemoLogin;

  /// Whether to list the development demo accounts (see AppConfig.showDemoAccounts).
  final bool showDemoAccounts;

  /// Set when the user is already signed in: replaces the Login actions.
  final VoidCallback? onDashboard;

  @override
  State<HomePage> createState() => _HomePageState();
}

enum _Section {
  home('Home'),
  about('About the System'),
  how('How It Works'),
  groups('User Groups'),
  demo('Demo Accounts'),
  faq('FAQ');

  const _Section(this.label);
  final String label;
}

class _HomePageState extends State<HomePage> {
  /// Demo accounts only make sense to visitors who are not signed in.
  bool get _showDemo => widget.showDemoAccounts && widget.onDashboard == null;

  final _scroll = ScrollController();
  final _keys = {for (final s in _Section.values) s: GlobalKey()};

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  void _go(_Section section) {
    final target = _keys[section]!.currentContext;
    if (target == null) return;
    final reduce = MediaQuery.of(context).disableAnimations;
    Scrollable.ensureVisible(
      target,
      duration: reduce ? Duration.zero : const Duration(milliseconds: 550),
      curve: Curves.easeInOutCubic,
    );
  }

  @override
  Widget build(BuildContext context) {
    final primaryAction = widget.onDashboard ?? widget.onLogin;
    final primaryLabel = widget.onDashboard == null ? 'Login' : 'Go to my dashboard';
    return Scaffold(
      backgroundColor: UsjColors.background,
      appBar: _NavBar(
        onSection: _go,
        actionLabel: primaryLabel,
        onAction: primaryAction,
        sections: [for (final s in _Section.values) if (s != _Section.demo || _showDemo) s],
      ),
      body: SingleChildScrollView(
        controller: _scroll,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _Hero(
              key: _keys[_Section.home],
              primaryLabel: widget.onDashboard == null ? 'Login to Get Started' : 'Go to my dashboard',
              onPrimary: primaryAction,
              onExplore: () => _go(_Section.how),
              onDemo: _showDemo ? () => _go(_Section.demo) : null,
            ),
            _SectionShell(key: _keys[_Section.about], title: 'About the System', subtitle: _aboutIntro,
                child: const _OverviewGrid()),
            _SectionShell(
              key: _keys[_Section.how],
              title: 'How It Works',
              subtitle: 'From your report to its resolution: every step is recorded and visible to you.',
              tinted: true,
              child: const _Workflow(),
            ),
            _SectionShell(
              key: _keys[_Section.groups],
              title: 'Who Uses the System',
              subtitle: 'Four groups, each with clearly separated responsibilities and permissions.',
              child: const _UserGroups(),
            ),
            const _SectionShell(
              title: 'Resolving Departments',
              subtitle: 'Each department sees only the cases a case administrator has assigned to it.',
              tinted: true,
              child: _Departments(),
            ),
            if (_showDemo)
              _SectionShell(
                key: _keys[_Section.demo],
                title: 'Try the System with Demo Accounts',
                subtitle: 'Sign in as any of these accounts to see how the system works for each user group.',
                tinted: true,
                child: _DemoAccounts(
                  onUse: (username) => widget.onDemoLogin != null
                      ? widget.onDemoLogin!(username, demoPassword)
                      : widget.onLogin(),
                ),
              ),
            const _SectionShell(title: 'Why Use It', child: _Benefits()),
            _SectionShell(
              key: _keys[_Section.faq],
              title: 'Frequently Asked Questions',
              tinted: true,
              child: const _Faq(),
            ),
            _FinalCta(label: primaryLabel, onPressed: primaryAction),
            _Footer(onSection: _go),
          ],
        ),
      ),
    );
  }
}

const _aboutIntro =
    'The FMSC Complaint & Suggestion Management System gives the faculty one structured, transparent channel '
    'for raising concerns and ideas, and for following what happens to them.';

// --- Navigation -------------------------------------------------------------------------------

class _NavBar extends StatelessWidget implements PreferredSizeWidget {
  const _NavBar({required this.onSection, required this.actionLabel, required this.onAction, required this.sections});
  final ValueChanged<_Section> onSection;
  final List<_Section> sections;
  final String actionLabel;
  final VoidCallback onAction;

  @override
  Size get preferredSize => const Size.fromHeight(72);

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.sizeOf(context).width;
    // Inline links only when they fit beside the logo, title and Login button.
    final wide = width >= 1360;
    return Material(
      color: UsjColors.surface,
      elevation: 1,
      child: SafeArea(
        bottom: false,
        child: Container(
          height: 72,
          decoration: const BoxDecoration(border: Border(bottom: BorderSide(color: UsjColors.yellow, width: 3))),
          padding: const EdgeInsets.symmetric(horizontal: Space.lg),
          child: Row(
            children: [
              Flexible(
                child: InkWell(
                  onTap: () => onSection(_Section.home),
                  borderRadius: BorderRadius.circular(Radii.sm),
                  child: Padding(
                    padding: const EdgeInsets.all(Space.xs),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        UsjLogo(size: width < 420 ? 36 : 44),
                        const SizedBox(width: Space.sm),
                        Flexible(
                          child: ConstrainedBox(
                            constraints: const BoxConstraints(maxWidth: 330),
                            child: Text(
                              'FMSC Complaint & Suggestion Management System',
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                              style: Theme.of(context).textTheme.titleSmall?.copyWith(
                                color: UsjColors.maroon,
                                fontWeight: FontWeight.w700,
                                height: 1.2,
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
              const SizedBox(width: Space.sm),
              if (wide)
                for (final s in sections)
                  TextButton(onPressed: () => onSection(s), child: Text(s.label))
              else
                PopupMenuButton<_Section>(
                  tooltip: 'Menu',
                  icon: const Icon(Icons.menu, color: UsjColors.maroon),
                  onSelected: onSection,
                  itemBuilder: (_) => [for (final s in sections) PopupMenuItem(value: s, child: Text(s.label))],
                ),
              const SizedBox(width: Space.sm),
              width < 420
                  ? FilledButton(onPressed: onAction, child: Text(actionLabel == 'Login' ? 'Login' : 'Dashboard'))
                  : FilledButton.icon(onPressed: onAction, icon: const Icon(Icons.login), label: Text(actionLabel)),
            ],
          ),
        ),
      ),
    );
  }
}

// --- Hero -------------------------------------------------------------------------------------

class _Hero extends StatelessWidget {
  const _Hero({super.key, required this.primaryLabel, required this.onPrimary, required this.onExplore, this.onDemo});
  final String primaryLabel;
  final VoidCallback onPrimary;
  final VoidCallback onExplore;
  final VoidCallback? onDemo;

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.sizeOf(context).width;
    final wide = width >= 900;
    final theme = Theme.of(context);
    final text = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          padding: const EdgeInsets.symmetric(horizontal: Space.md, vertical: Space.xs),
          decoration: BoxDecoration(color: UsjColors.yellow, borderRadius: BorderRadius.circular(Radii.pill)),
          child: const Text(
            'Faculty of Management Studies and Commerce',
            style: TextStyle(color: UsjColors.textPrimary, fontWeight: FontWeight.w700),
          ),
        ),
        const SizedBox(height: Space.lg),
        Semantics(
          header: true,
          child: Text(
            "Your Voice Matters. Let's Improve Our Faculty Together.",
            style: (wide ? theme.textTheme.displaySmall : theme.textTheme.headlineMedium)?.copyWith(
              color: Colors.white,
              fontWeight: FontWeight.w800,
              height: 1.15,
            ),
          ),
        ),
        const SizedBox(height: Space.lg),
        Text(
          'The FMSC Complaint & Suggestion Management System provides a structured and transparent way for '
          'students, lecturers, and non-academic staff to raise concerns, submit suggestions, and follow the '
          'progress of reported issues.',
          style: theme.textTheme.titleMedium?.copyWith(color: Colors.white, fontWeight: FontWeight.w400, height: 1.5),
        ),
        const SizedBox(height: Space.xl),
        Wrap(
          spacing: Space.md,
          runSpacing: Space.md,
          children: [
            FilledButton.icon(
              onPressed: onPrimary,
              style: FilledButton.styleFrom(
                backgroundColor: UsjColors.yellow,
                foregroundColor: UsjColors.textPrimary,
                minimumSize: const Size(200, 52),
              ),
              icon: const Icon(Icons.arrow_forward),
              label: Text(primaryLabel),
            ),
            OutlinedButton.icon(
              onPressed: onExplore,
              style: OutlinedButton.styleFrom(
                foregroundColor: Colors.white,
                side: const BorderSide(color: Colors.white, width: 1.5),
                minimumSize: const Size(200, 52),
              ),
              icon: const Icon(Icons.south),
              label: const Text('Explore How It Works'),
            ),
            if (onDemo != null)
              TextButton.icon(
                onPressed: onDemo,
                style: TextButton.styleFrom(foregroundColor: UsjColors.yellow, minimumSize: const Size(200, 52)),
                icon: const Icon(Icons.badge_outlined),
                label: const Text('Try a demo account'),
              ),
          ],
        ),
      ],
    );
    return Container(
      color: UsjColors.maroon,
      child: Stack(
        children: [
          // Decorative shapes in official palette colours (purely visual).
          const Positioned(right: -60, top: -60, child: _Blob(size: 240, color: UsjColors.red)),
          const Positioned(left: -40, bottom: -70, child: _Blob(size: 200, color: UsjColors.gold, opacity: 0.35)),
          Positioned(right: width * 0.38, bottom: -30, child: const _Blob(size: 90, color: UsjColors.yellow, opacity: 0.5)),
          Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 1180),
              child: Padding(
                padding: EdgeInsets.symmetric(horizontal: Space.xl, vertical: wide ? 72 : 40),
                child: wide
                    ? Row(
                        children: [
                          Expanded(flex: 6, child: _Reveal(child: text)),
                          const SizedBox(width: Space.xxl),
                          const Expanded(flex: 4, child: _Reveal(delay: 150, child: _HeroIllustration())),
                        ],
                      )
                    : Column(
                        children: [
                          _Reveal(child: text),
                          const SizedBox(height: Space.xl),
                          const _Reveal(delay: 150, child: _HeroIllustration()),
                        ],
                      ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _Blob extends StatelessWidget {
  const _Blob({required this.size, required this.color, this.opacity = 0.55});
  final double size;
  final Color color;
  final double opacity;

  @override
  Widget build(BuildContext context) => ExcludeSemantics(
    child: Container(
      width: size,
      height: size,
      decoration: BoxDecoration(color: color.withValues(alpha: opacity), shape: BoxShape.circle),
    ),
  );
}

/// A small, decorative "journey" of a case: submitted → assigned → resolved.
class _HeroIllustration extends StatelessWidget {
  const _HeroIllustration();

  @override
  Widget build(BuildContext context) {
    const steps = [
      (Icons.edit_note, 'Complaint submitted', UsjColors.red),
      (Icons.manage_search, 'Reviewed by a case administrator', UsjColors.blue),
      (Icons.apartment, 'Assigned to a department', UsjColors.gold),
      (Icons.task_alt, 'Resolved and explained', UsjColors.success),
    ];
    return Semantics(
      label: 'Illustration: a complaint is submitted, reviewed, assigned to a department and resolved.',
      excludeSemantics: true,
      child: Container(
        padding: const EdgeInsets.all(Space.lg),
        decoration: BoxDecoration(
          color: UsjColors.surface,
          borderRadius: BorderRadius.circular(20),
          boxShadow: const [BoxShadow(color: Color(0x33000000), blurRadius: 24, offset: Offset(0, 10))],
        ),
        child: Column(
          children: [
            for (var i = 0; i < steps.length; i++) ...[
              Row(
                children: [
                  CircleAvatar(
                    radius: 22,
                    backgroundColor: steps[i].$3.withValues(alpha: 0.15),
                    child: Icon(steps[i].$1, color: steps[i].$3 == UsjColors.gold ? UsjColors.warning : steps[i].$3),
                  ),
                  const SizedBox(width: Space.md),
                  Expanded(child: Text(steps[i].$2, style: const TextStyle(fontWeight: FontWeight.w600))),
                ],
              ),
              if (i < steps.length - 1)
                Padding(
                  padding: const EdgeInsets.only(left: 21),
                  child: Align(
                    alignment: Alignment.centerLeft,
                    child: Container(width: 2, height: 18, color: UsjColors.border),
                  ),
                ),
            ],
          ],
        ),
      ),
    );
  }
}

// --- Section scaffolding ------------------------------------------------------------------------

class _SectionShell extends StatelessWidget {
  const _SectionShell({super.key, required this.title, required this.child, this.subtitle, this.tinted = false});
  final String title;
  final String? subtitle;
  final Widget child;
  final bool tinted;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      color: tinted ? UsjColors.surface : UsjColors.background,
      padding: const EdgeInsets.symmetric(horizontal: Space.xl, vertical: 56),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 1180),
          child: _Reveal(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(width: 56, height: 5, decoration: BoxDecoration(color: UsjColors.red,
                    borderRadius: BorderRadius.circular(3))),
                const SizedBox(height: Space.md),
                Semantics(
                  header: true,
                  child: Text(title, style: theme.textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800)),
                ),
                if (subtitle != null) ...[
                  const SizedBox(height: Space.sm),
                  ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 760),
                    child: Text(subtitle!,
                        style: theme.textTheme.titleMedium?.copyWith(
                            color: UsjColors.textSecondary, fontWeight: FontWeight.w400)),
                  ),
                ],
                const SizedBox(height: Space.xl),
                child,
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Responsive grid: 1, 2, 3 or 4 columns by width.
class _Grid extends StatelessWidget {
  const _Grid({required this.children, this.maxColumns = 3});
  final List<Widget> children;
  final int maxColumns;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, c) {
        final columns = (c.maxWidth >= 1000 ? 4 : c.maxWidth >= 700 ? 3 : c.maxWidth >= 480 ? 2 : 1)
            .clamp(1, maxColumns);
        final width = (c.maxWidth - Space.lg * (columns - 1)) / columns;
        return Wrap(
          spacing: Space.lg,
          runSpacing: Space.lg,
          children: [for (final child in children) SizedBox(width: width, child: child)],
        );
      },
    );
  }
}

/// Card that lifts slightly on hover or keyboard focus (desktop/web).
class _HoverCard extends StatefulWidget {
  const _HoverCard({required this.child, this.accent});
  final Widget child;
  final Color? accent;

  @override
  State<_HoverCard> createState() => _HoverCardState();
}

class _HoverCardState extends State<_HoverCard> {
  bool _hover = false;

  @override
  Widget build(BuildContext context) {
    final reduce = MediaQuery.of(context).disableAnimations;
    return FocusableActionDetector(
      onShowHoverHighlight: (v) => setState(() => _hover = v),
      onShowFocusHighlight: (v) => setState(() => _hover = v),
      child: AnimatedContainer(
        duration: reduce ? Duration.zero : const Duration(milliseconds: 180),
        transform: Matrix4.translationValues(0, _hover ? -4 : 0, 0),
        decoration: BoxDecoration(
          color: UsjColors.surface,
          borderRadius: BorderRadius.circular(Radii.md),
          border: Border.all(color: _hover ? (widget.accent ?? UsjColors.blue) : UsjColors.border, width: 1.5),
          boxShadow: _hover ? const [BoxShadow(color: Color(0x1F000000), blurRadius: 18, offset: Offset(0, 8))] : null,
        ),
        child: ClipRRect(borderRadius: BorderRadius.circular(Radii.md), child: widget.child),
      ),
    );
  }
}

class _IconBadge extends StatelessWidget {
  const _IconBadge(this.icon, this.color);
  final IconData icon;
  final Color color;

  @override
  Widget build(BuildContext context) => Container(
    width: 52,
    height: 52,
    decoration: BoxDecoration(color: color.withValues(alpha: 0.14), borderRadius: BorderRadius.circular(14)),
    // Gold and yellow are too light for icons on white, so use the warning ink with them.
    child: Icon(icon, color: color == UsjColors.gold || color == UsjColors.yellow ? UsjColors.warning : color, size: 28),
  );
}

/// Fades and slides content in the first time it scrolls into view.
/// Respects the platform "reduce motion" setting.
class _Reveal extends StatefulWidget {
  const _Reveal({required this.child, this.delay = 0});
  final Widget child;
  final int delay;

  @override
  State<_Reveal> createState() => _RevealState();
}

class _RevealState extends State<_Reveal> {
  bool _shown = false;
  ScrollPosition? _position;
  Timer? _delay;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (MediaQuery.of(context).disableAnimations) {
      _shown = true;
      return;
    }
    _position?.removeListener(_check);
    _position = Scrollable.maybeOf(context)?.position;
    _position?.addListener(_check);
    WidgetsBinding.instance.addPostFrameCallback((_) => _check());
  }

  void _check() {
    if (_shown || !mounted) return;
    final box = context.findRenderObject() as RenderBox?;
    if (box == null || !box.hasSize) return;
    final top = box.localToGlobal(Offset.zero).dy;
    if (top < MediaQuery.sizeOf(context).height - 40) {
      _delay = Timer(Duration(milliseconds: widget.delay), () {
        if (mounted) setState(() => _shown = true);
      });
      _position?.removeListener(_check);
    }
  }

  @override
  void dispose() {
    _delay?.cancel();
    _position?.removeListener(_check);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedOpacity(
      opacity: _shown ? 1 : 0,
      duration: const Duration(milliseconds: 500),
      curve: Curves.easeOut,
      child: AnimatedSlide(
        offset: _shown ? Offset.zero : const Offset(0, 0.04),
        duration: const Duration(milliseconds: 500),
        curve: Curves.easeOutCubic,
        child: widget.child,
      ),
    );
  }
}

// --- Content sections -----------------------------------------------------------------------------

class _OverviewGrid extends StatelessWidget {
  const _OverviewGrid();

  static const _items = [
    (Icons.flag_outlined, UsjColors.red, 'Why it exists',
        'Issues were often raised informally and were hard to follow up. This system records every '
            'complaint and suggestion in one place.'),
    (Icons.groups_outlined, UsjColors.blue, 'Who can submit',
        'Students, lecturers and non-academic staff can submit complaints and suggestions with their faculty account.'),
    (Icons.manage_search, UsjColors.gold, 'How cases are reviewed',
        'A case administrator reads each new submission and decides how it should be handled.'),
    (Icons.alt_route, UsjColors.maroon, 'Assignment to departments',
        'Each complaint is assigned to the responsible department with a message explaining why.'),
    (Icons.forum_outlined, UsjColors.blue, 'Updates with explanations',
        'Every status change made by staff must include a message, so you always know what happened and why.'),
    (Icons.track_changes, UsjColors.red, 'Follow your submissions',
        'Your dashboard shows the status and full progress history of everything you submitted, and only yours.'),
    (Icons.verified_user_outlined, UsjColors.gold, 'Accountability',
        'Who did what, and when, is recorded in a history that cannot be edited or deleted.'),
  ];

  @override
  Widget build(BuildContext context) {
    return _Grid(
      maxColumns: 4,
      children: [
        for (final (icon, color, title, body) in _items)
          _HoverCard(
            accent: color,
            child: Padding(
              padding: const EdgeInsets.all(Space.lg),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _IconBadge(icon, color),
                  const SizedBox(height: Space.md),
                  Text(title, style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: Space.sm),
                  Text(body, style: const TextStyle(color: UsjColors.textSecondary, height: 1.5)),
                ],
              ),
            ),
          ),
      ],
    );
  }
}

class _Workflow extends StatelessWidget {
  const _Workflow();

  static const _steps = [
    (Icons.edit_note, 'Submit a complaint or suggestion', 'Describe the issue or idea, its category and location.'),
    (Icons.manage_search, 'A case administrator reviews it', 'New submissions appear in the review queue.'),
    (Icons.assignment_ind_outlined, 'It is assigned to a department',
        'The case administrator chooses the resolving department and explains the choice.'),
    (Icons.engineering_outlined, 'The department processes the case', 'Only the assigned department can see and act on it.'),
    (Icons.campaign_outlined, 'Status updates and progress messages',
        'Every status change is saved together with a message from the department.'),
    (Icons.visibility_outlined, 'You track the progress', 'Open the case from your dashboard to see its full history.'),
    (Icons.task_alt, 'The department records the resolution',
        'You can read what was done, confirm it, or reopen the case if the problem continues.'),
  ];

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, c) {
        final wide = c.maxWidth >= 900;
        final cards = [
          for (var i = 0; i < _steps.length; i++)
            _HoverCard(
              accent: i.isEven ? UsjColors.red : UsjColors.blue,
              child: Padding(
                padding: const EdgeInsets.all(Space.lg),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Semantics(
                      label: 'Step ${i + 1}',
                      excludeSemantics: true,
                      child: CircleAvatar(
                        radius: 20,
                        backgroundColor: i.isEven ? UsjColors.red : UsjColors.blue,
                        child: Text('${i + 1}', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w800)),
                      ),
                    ),
                    const SizedBox(width: Space.md),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(children: [
                            Icon(_steps[i].$1, size: 20, color: UsjColors.textSecondary),
                            const SizedBox(width: Space.xs),
                            Expanded(child: Text(_steps[i].$2, style: Theme.of(context).textTheme.titleSmall)),
                          ]),
                          const SizedBox(height: Space.xs),
                          Text(_steps[i].$3, style: const TextStyle(color: UsjColors.textSecondary, height: 1.45)),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
        ];
        if (!wide) {
          return Column(
            children: [
              for (var i = 0; i < cards.length; i++) ...[
                cards[i],
                if (i < cards.length - 1)
                  const ExcludeSemantics(
                    child: Padding(
                      padding: EdgeInsets.symmetric(vertical: Space.xs),
                      child: Icon(Icons.keyboard_arrow_down, color: UsjColors.gold),
                    ),
                  ),
              ],
            ],
          );
        }
        return _Grid(maxColumns: 4, children: cards);
      },
    );
  }
}

class _UserGroups extends StatelessWidget {
  const _UserGroups();

  static const _groups = [
    (Icons.record_voice_over_outlined, UsjColors.red, 'Complainers', 'Students · Lecturers · Non-academic staff', [
      'Submit complaints and suggestions',
      'See only their own submissions',
      'Follow status and progress messages',
      'Confirm a resolution or reopen a case',
    ]),
    (Icons.monitor_heart_outlined, UsjColors.blue, 'Admins', 'Faculty-wide monitoring', [
      'View the faculty-wide dashboard',
      'Read every case and its history',
      'Add administrative messages to cases',
      'Do not change statuses or assignments',
    ]),
    (Icons.fact_check_outlined, UsjColors.gold, 'Case Administrators', 'Review and assignment', [
      'Review new complaints',
      'Assign each case to the right department',
      'Explain every decision with a message',
      'Monitor progress and reassign when needed',
    ]),
    (Icons.apartment_outlined, UsjColors.maroon, 'Resolving Departments', 'Process assigned cases', [
      'See only cases assigned to their department',
      'Update the status with an explanatory message',
      'Record the resolution details',
      'Cannot see other departments\' cases',
    ]),
  ];

  @override
  Widget build(BuildContext context) {
    return _Grid(
      maxColumns: 4,
      children: [
        for (final (icon, color, title, who, duties) in _groups)
          _HoverCard(
            accent: color,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Container(height: 6, color: color),
                Padding(
                  padding: const EdgeInsets.all(Space.lg),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      _IconBadge(icon, color),
                      const SizedBox(height: Space.md),
                      Text(title, style: Theme.of(context).textTheme.titleMedium),
                      Text(who, style: const TextStyle(color: UsjColors.textSecondary)),
                      const SizedBox(height: Space.md),
                      for (final d in duties)
                        Padding(
                          padding: const EdgeInsets.only(bottom: Space.xs),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Padding(
                                padding: EdgeInsets.only(top: 2),
                                child: Icon(Icons.check_circle_outline, size: 18, color: UsjColors.success),
                              ),
                              const SizedBox(width: Space.sm),
                              Expanded(child: Text(d)),
                            ],
                          ),
                        ),
                    ],
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }
}

class _Departments extends StatelessWidget {
  const _Departments();

  static const _items = [
    (Icons.computer_outlined, UsjColors.blue, 'IT Department'),
    (Icons.build_outlined, UsjColors.gold, 'Maintenance Department'),
    (Icons.assignment_outlined, UsjColors.red, 'Examination Unit'),
    (Icons.account_balance_outlined, UsjColors.maroon, "Dean's Office"),
  ];

  @override
  Widget build(BuildContext context) {
    return _Grid(
      maxColumns: 4,
      children: [
        for (final (icon, color, name) in _items)
          _HoverCard(
            accent: color,
            child: Padding(
              padding: const EdgeInsets.all(Space.lg),
              child: Row(
                children: [
                  _IconBadge(icon, color),
                  const SizedBox(width: Space.md),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(name, style: Theme.of(context).textTheme.titleMedium),
                        const Text('Handles the cases assigned to it',
                            style: TextStyle(color: UsjColors.textSecondary)),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
      ],
    );
  }
}

/// Development demo accounts (from seed_demo_users), grouped by user group.
class _DemoAccounts extends StatelessWidget {
  const _DemoAccounts({required this.onUse});
  final ValueChanged<String> onUse;

  static const _groupColors = {
    'Complainers': UsjColors.red,
    'Admins': UsjColors.blue,
    'Case Administrators': UsjColors.gold,
    'Resolving Departments': UsjColors.maroon,
    'Read-only viewer': UsjColors.neutral,
  };

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Semantics(
          container: true,
          child: Container(
            padding: const EdgeInsets.all(Space.lg),
            decoration: BoxDecoration(
              color: UsjColors.warningBg,
              borderRadius: BorderRadius.circular(Radii.md),
              border: Border.all(color: UsjColors.gold),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Icon(Icons.info_outline, color: UsjColors.warning),
                const SizedBox(width: Space.md),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Wrap(
                        crossAxisAlignment: WrapCrossAlignment.center,
                        spacing: Space.sm,
                        children: [
                          const Text('Password for every demo account:', style: TextStyle(fontWeight: FontWeight.w700)),
                          _Copyable(text: demoPassword, label: 'password'),
                        ],
                      ),
                      const SizedBox(height: Space.xs),
                      const Text(
                        'For demonstration and testing only. These accounts exist only on development databases '
                        '(created with "python manage.py seed_demo_users"). Never use this password for a real account.',
                        style: TextStyle(color: UsjColors.warning, height: 1.45),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: Space.lg),
        _Grid(
          maxColumns: 3,
          children: [
            for (final a in demoAccounts)
              _HoverCard(
                accent: _groupColors[a.group],
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Container(height: 5, color: _groupColors[a.group]),
                    Padding(
                      padding: const EdgeInsets.all(Space.lg),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(a.group.toUpperCase(),
                              style: theme.textTheme.labelSmall?.copyWith(
                                  color: UsjColors.textSecondary, letterSpacing: 0.8, fontWeight: FontWeight.w700)),
                          const SizedBox(height: Space.xs),
                          Text(a.role, style: theme.textTheme.titleMedium),
                          const SizedBox(height: Space.sm),
                          _Copyable(text: a.username, label: 'username'),
                          const SizedBox(height: Space.sm),
                          Text('Opens: ${a.landsOn}', style: const TextStyle(color: UsjColors.textSecondary)),
                          const SizedBox(height: Space.xs),
                          Text(a.tryThis, style: const TextStyle(height: 1.45)),
                          const SizedBox(height: Space.md),
                          Semantics(
                            button: true,
                            label: 'Sign in as ${a.username}',
                            excludeSemantics: true,
                            child: OutlinedButton.icon(
                              onPressed: () => onUse(a.username),
                              icon: const Icon(Icons.login, size: 18),
                              label: const Text('Sign in as this user'),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
          ],
        ),
      ],
    );
  }
}

/// Monospace value with a copy button (usernames and the demo password).
class _Copyable extends StatelessWidget {
  const _Copyable({required this.text, required this.label});
  final String text;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.only(left: Space.sm),
      decoration: BoxDecoration(
        color: UsjColors.surfaceMuted,
        borderRadius: BorderRadius.circular(Radii.sm),
        border: Border.all(color: UsjColors.border),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Flexible(
            child: SelectableText(text,
                style: const TextStyle(fontFamily: 'monospace', fontWeight: FontWeight.w700, fontSize: 15)),
          ),
          IconButton(
            tooltip: 'Copy $label',
            iconSize: 18,
            icon: const Icon(Icons.copy),
            onPressed: () {
              Clipboard.setData(ClipboardData(text: text));
              ScaffoldMessenger.maybeOf(context)
                ?..hideCurrentSnackBar()
                ..showSnackBar(SnackBar(content: Text('Copied $label "$text"')));
            },
          ),
        ],
      ),
    );
  }
}

class _Benefits extends StatelessWidget {
  const _Benefits();

  static const _items = [
    'A structured submission process',
    'A clear reference number for every case',
    'Easier progress tracking',
    'Organised departmental assignments',
    'Recorded status updates and messages',
    'Better visibility for authorised administrators',
    'One central place for suggestions',
  ];

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: Space.md,
      runSpacing: Space.md,
      children: [
        for (var i = 0; i < _items.length; i++)
          Container(
            padding: const EdgeInsets.symmetric(horizontal: Space.lg, vertical: Space.md),
            decoration: BoxDecoration(
              color: [UsjColors.paleBlue, UsjColors.softYellow.withValues(alpha: 0.35),
                UsjColors.red.withValues(alpha: 0.08)][i % 3],
              borderRadius: BorderRadius.circular(Radii.pill),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.check, size: 18, color: UsjColors.textPrimary),
                const SizedBox(width: Space.sm),
                Flexible(child: Text(_items[i], style: const TextStyle(fontWeight: FontWeight.w600))),
              ],
            ),
          ),
      ],
    );
  }
}

class _Faq extends StatelessWidget {
  const _Faq();

  static const _items = [
    ('Who can submit a complaint?',
        'Students, lecturers and non-academic staff of the faculty can submit complaints after signing in.'),
    ('Can I submit a suggestion?',
        'Yes. Choose "Suggestion" when submitting. A case administrator evaluates it and it may be accepted, '
            'planned, implemented or declined. A declined suggestion always comes with a reason.'),
    ("Can I see another person's complaint?",
        'No. You can only see what you submitted. Staff see cases only as their role allows, and each department '
            'sees only the cases assigned to it.'),
    ('Who reviews my complaint?', 'A case administrator reviews every new complaint.'),
    ('How is a complaint assigned to a department?',
        'The case administrator chooses the responsible department (IT Department, Maintenance Department, '
            "Examination Unit or Dean's Office) and records a message explaining the choice."),
    ('How can I track a complaint?',
        'Sign in and open the case from your dashboard. You will see its current status and progress history. '
            'You also get a notification when something changes.'),
    ('Can I see status updates?',
        'Yes. Every status change made by staff includes a message, and you can read it in the case history.'),
    ('Which departments handle complaints?',
        "The IT Department, the Maintenance Department, the Examination Unit and the Dean's Office."),
    ('Who should I contact if I cannot log in?',
        'Please contact the faculty administration. Accounts and password resets are handled by the system '
            'administrator.'),
  ];

  @override
  Widget build(BuildContext context) {
    // A Material surface (not a coloured box) so the tiles' ink and focus highlights show.
    return Material(
      color: UsjColors.background,
      clipBehavior: Clip.antiAlias,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(Radii.md),
        side: const BorderSide(color: UsjColors.border),
      ),
      child: Column(
        children: [
          for (var i = 0; i < _items.length; i++) ...[
            ExpansionTile(
              leading: const Icon(Icons.help_outline, color: UsjColors.blue),
              title: Text(_items[i].$1, style: const TextStyle(fontWeight: FontWeight.w600)),
              childrenPadding: const EdgeInsets.fromLTRB(Space.xl * 2, 0, Space.lg, Space.lg),
              expandedCrossAxisAlignment: CrossAxisAlignment.start,
              children: [Text(_items[i].$2, style: const TextStyle(height: 1.5))],
            ),
            if (i < _items.length - 1) const Divider(height: 1),
          ],
        ],
      ),
    );
  }
}

class _FinalCta extends StatelessWidget {
  const _FinalCta({required this.label, required this.onPressed});
  final String label;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      color: UsjColors.red,
      padding: const EdgeInsets.symmetric(horizontal: Space.xl, vertical: 56),
      child: Stack(
        alignment: Alignment.center,
        children: [
          const Positioned(left: -40, top: -60, child: _Blob(size: 160, color: UsjColors.yellow, opacity: 0.3)),
          Column(
            children: [
              Semantics(
                header: true,
                child: Text('Have a Concern or an Idea to Share?',
                    textAlign: TextAlign.center,
                    style: theme.textTheme.headlineSmall?.copyWith(color: Colors.white, fontWeight: FontWeight.w800)),
              ),
              const SizedBox(height: Space.md),
              ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 640),
                child: Text(
                  'Sign in to submit a complaint or suggestion and follow its progress through the appropriate '
                  'university process.',
                  textAlign: TextAlign.center,
                  style: theme.textTheme.titleMedium?.copyWith(color: Colors.white, fontWeight: FontWeight.w400),
                ),
              ),
              const SizedBox(height: Space.xl),
              FilledButton.icon(
                onPressed: onPressed,
                style: FilledButton.styleFrom(
                  backgroundColor: UsjColors.yellow,
                  foregroundColor: UsjColors.textPrimary,
                  minimumSize: const Size(220, 52),
                ),
                icon: const Icon(Icons.login),
                label: Text(label),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _Footer extends StatelessWidget {
  const _Footer({required this.onSection});
  final ValueChanged<_Section> onSection;

  @override
  Widget build(BuildContext context) {
    const light = TextStyle(color: Color(0xFFE8E8EC));
    return Container(
      color: UsjColors.textPrimary,
      padding: const EdgeInsets.symmetric(horizontal: Space.xl, vertical: Space.xxl),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 1180),
          child: Wrap(
            spacing: Space.xxl,
            runSpacing: Space.xl,
            alignment: WrapAlignment.spaceBetween,
            children: [
              ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 460),
                child: const Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('University of Sri Jayewardenepura',
                        style: TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 16)),
                    SizedBox(height: Space.xs),
                    Text('Faculty of Management Studies and Commerce', style: light),
                    SizedBox(height: Space.xs),
                    Text('FMSC Complaint & Suggestion Management System', style: light),
                  ],
                ),
              ),
              Wrap(
                spacing: Space.sm,
                children: [
                  for (final s in _Section.values.where((s) => s != _Section.demo))
                    TextButton(
                      onPressed: () => onSection(s),
                      style: TextButton.styleFrom(foregroundColor: UsjColors.yellow),
                      child: Text(s.label),
                    ),
                ],
              ),
              Text('© ${DateTime.now().year} Faculty of Management Studies and Commerce, '
                  'University of Sri Jayewardenepura.', style: light),
            ],
          ),
        ),
      ),
    );
  }
}
