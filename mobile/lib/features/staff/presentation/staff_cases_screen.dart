import 'package:flutter/material.dart';

import '../../../core/api_client.dart';
import '../../../design/theme.dart';
import '../../../design/usj_colors.dart';
import '../../../design/widgets.dart';
import '../../../platform/paged_list.dart';
import '../../../platform/platform_scope.dart';
import '../../cases/case_routes.dart';
import '../data/staff_cases.dart';

/// Status filters (Hick's law: five, plus "All").
enum CaseStatusFilter {
  all('All', null),
  review('Awaiting review', 'submitted,under_review,reopened'),
  assigned('Assigned', 'assigned'),
  active('In progress', 'in_progress,waiting_for_information'),
  resolved('Resolved', 'solved,closed'),
  rejected('Rejected', 'rejected');

  const CaseStatusFilter(this.label, this.statuses);
  final String label;
  final String? statuses;
}

const _complainerTypes = {
  'student': 'Students',
  'lecturer': 'Lecturers',
  'non_academic_staff': 'Non-academic staff',
};

/// Case list for admins, case administrators and resolving departments. The
/// server returns only the cases the user may see (all, or own department).
class StaffCasesScreen extends StatefulWidget {
  const StaffCasesScreen({super.key});

  @override
  State<StaffCasesScreen> createState() => _StaffCasesScreenState();
}

class _StaffCasesScreenState extends State<StaffCasesScreen> {
  final _search = TextEditingController();
  CaseStatusFilter _status = CaseStatusFilter.all;
  String _query = '';
  int? _department;
  String? _submitterRole;
  List<({int id, String name})> _departments = const [];
  int _reload = 0;
  bool _started = false;

  bool get _facultyWide => !(PlatformScope.of(context).session.user?.isDepartment ?? true);

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_started) {
      _started = true;
      if (_facultyWide && (PlatformScope.of(context).session.user?.reviewsCases ?? false)) _loadDepartments();
    }
  }

  Future<void> _loadDepartments() async {
    try {
      final list = await PlatformScope.of(context).staffCases.departments();
      if (mounted) setState(() => _departments = list);
    } on ApiException {
      // The department filter is optional; the list still works without it.
    }
  }

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  StaffCaseFilter get _filter => StaffCaseFilter(
    statuses: _status.statuses,
    search: _query,
    departmentId: _department,
    submitterRole: _submitterRole,
  );

  Future<void> _open(StaffCaseRow row) async {
    await CaseRoutes.openCase(context, row.id);
    if (mounted) setState(() => _reload++);
  }

  @override
  Widget build(BuildContext context) {
    final scope = PlatformScope.of(context);
    final user = scope.session.user;
    final title = user?.isDepartment == true && (user?.authorities.isNotEmpty ?? false)
        ? '${user!.authorities.first.name} cases'
        : 'All cases';
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(Space.lg, Space.md, Space.lg, 0),
            child: TextField(
              controller: _search,
              textInputAction: TextInputAction.search,
              onSubmitted: (v) => setState(() => _query = v),
              decoration: InputDecoration(
                labelText: 'Search by title, reference or location',
                prefixIcon: const Icon(Icons.search),
                suffixIcon: _query.isEmpty
                    ? null
                    : IconButton(
                        tooltip: 'Clear search',
                        icon: const Icon(Icons.clear),
                        onPressed: () => setState(() {
                          _search.clear();
                          _query = '';
                        }),
                      ),
              ),
            ),
          ),
          SizedBox(
            height: kMinTouchTarget + Space.lg,
            child: ListView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: Space.lg, vertical: Space.sm),
              children: [
                for (final f in CaseStatusFilter.values)
                  Padding(
                    padding: const EdgeInsets.only(right: Space.sm),
                    child: ChoiceChip(
                      label: Text(f.label),
                      selected: f == _status,
                      onSelected: (_) => setState(() => _status = f),
                    ),
                  ),
              ],
            ),
          ),
          if (_facultyWide)
            Padding(
              padding: const EdgeInsets.fromLTRB(Space.lg, 0, Space.lg, Space.sm),
              child: Row(
                children: [
                  if (_departments.isNotEmpty) ...[
                    Expanded(
                      child: DropdownButtonFormField<int?>(
                        initialValue: _department,
                        isExpanded: true,
                        decoration: const InputDecoration(labelText: 'Department'),
                        items: [
                          const DropdownMenuItem<int?>(value: null, child: Text('All departments')),
                          for (final d in _departments) DropdownMenuItem<int?>(value: d.id, child: Text(d.name)),
                        ],
                        onChanged: (v) => setState(() => _department = v),
                      ),
                    ),
                    const SizedBox(width: Space.md),
                  ],
                  Expanded(
                    child: DropdownButtonFormField<String?>(
                      initialValue: _submitterRole,
                      isExpanded: true,
                      decoration: const InputDecoration(labelText: 'Complainant type'),
                      items: [
                        const DropdownMenuItem<String?>(value: null, child: Text('Everyone')),
                        for (final e in _complainerTypes.entries)
                          DropdownMenuItem<String?>(value: e.key, child: Text(e.value)),
                      ],
                      onChanged: (v) => setState(() => _submitterRole = v),
                    ),
                  ),
                ],
              ),
            ),
          Expanded(
            child: PagedList<StaffCaseRow>(
              reloadKey: (_filter.toQuery(1).toString(), _reload),
              loadingMessage: 'Loading cases…',
              load: (page) => scope.staffCases.list(_filter, page: page),
              header: (context, count) => Padding(
                padding: const EdgeInsets.fromLTRB(Space.lg, Space.sm, Space.lg, Space.xs),
                child: Text('$count case${count == 1 ? '' : 's'}', style: Theme.of(context).textTheme.titleSmall),
              ),
              empty: MessageView(
                icon: Icons.inbox_outlined,
                title: 'No cases match',
                message: user?.isDepartment == true
                    ? 'Cases appear here once a case administrator assigns them to your department.'
                    : 'Try another status or clear the search.',
              ),
              itemBuilder: (context, row, _) => ListTile(
                minTileHeight: kMinTouchTarget + 16,
                title: Text(row.title, maxLines: 2, overflow: TextOverflow.ellipsis),
                subtitle: Padding(
                  padding: const EdgeInsets.only(top: Space.xs),
                  child: Wrap(
                    spacing: Space.sm,
                    runSpacing: Space.xs,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      Text(
                        [
                          row.caseNumber,
                          if (row.caseType == 'suggestion') 'Suggestion',
                          ?row.submitterType,
                          row.department ?? 'Unassigned',
                        ].join(' · '),
                        style: const TextStyle(color: UsjColors.textSecondary),
                      ),
                      StatusBadge(status: row.status, label: row.statusLabel),
                      if (row.priority == 'urgent') const PriorityBadge(priority: 'urgent'),
                      if (row.isOverdue) const OverdueBadge(),
                    ],
                  ),
                ),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => _open(row),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
