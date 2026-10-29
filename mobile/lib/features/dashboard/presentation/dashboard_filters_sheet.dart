import 'package:flutter/material.dart';

import '../../../design/theme.dart';
import '../data/dashboard.dart';

/// Optional refinements, kept out of the main screen (progressive disclosure).
/// The date range is chosen on the dashboard itself.
class DashboardFiltersSheet extends StatefulWidget {
  const DashboardFiltersSheet({
    super.key,
    required this.initial,
    required this.categories,
    required this.units,
    required this.statuses,
  });

  final DashboardFilters initial;
  final List<({int id, String name})> categories;
  final List<({int id, String name})> units;
  final List<({String value, String label})> statuses;

  @override
  State<DashboardFiltersSheet> createState() => _DashboardFiltersSheetState();
}

class _DashboardFiltersSheetState extends State<DashboardFiltersSheet> {
  late int? _category = widget.initial.categoryId;
  late int? _unit = widget.initial.authorityId;
  late String? _priority = widget.initial.priority;
  late String? _type = widget.initial.caseType;
  late String? _status = widget.initial.status;
  late final _location = TextEditingController(text: widget.initial.location);

  @override
  void dispose() {
    _location.dispose();
    super.dispose();
  }

  DashboardFilters _result() => DashboardFilters(
    dateFrom: widget.initial.dateFrom,
    dateTo: widget.initial.dateTo,
    categoryId: _category,
    authorityId: _unit,
    priority: _priority,
    caseType: _type,
    status: _status,
    location: _location.text,
  );

  Widget _dropdown<T>(String label, T? value, List<DropdownMenuItem<T?>> items, ValueChanged<T?> onChanged) =>
      Padding(
        padding: const EdgeInsets.only(bottom: Space.md),
        child: DropdownButtonFormField<T?>(
          initialValue: value,
          isExpanded: true,
          decoration: InputDecoration(labelText: label),
          items: [DropdownMenuItem<T?>(value: null, child: const Text('All')), ...items],
          onChanged: onChanged,
        ),
      );

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      mainAxisSize: MainAxisSize.min,
      children: [
        _dropdown<String>('Case type', _type, const [
          DropdownMenuItem(value: 'complaint', child: Text('Complaints')),
          DropdownMenuItem(value: 'suggestion', child: Text('Suggestions')),
        ], (v) => setState(() => _type = v)),
        _dropdown<int>('Category', _category, [
          for (final c in widget.categories) DropdownMenuItem(value: c.id, child: Text(c.name)),
        ], (v) => setState(() => _category = v)),
        _dropdown<String>('Priority', _priority, const [
          DropdownMenuItem(value: 'urgent', child: Text('Urgent')),
          DropdownMenuItem(value: 'normal', child: Text('Normal')),
        ], (v) => setState(() => _priority = v)),
        _dropdown<String>('Status', _status, [
          for (final s in widget.statuses) DropdownMenuItem(value: s.value, child: Text(s.label)),
        ], (v) => setState(() => _status = v)),
        if (widget.units.isNotEmpty)
          _dropdown<int>('Responsible unit', _unit, [
            for (final u in widget.units) DropdownMenuItem(value: u.id, child: Text(u.name)),
          ], (v) => setState(() => _unit = v)),
        TextField(
          controller: _location,
          decoration: const InputDecoration(labelText: 'Location contains', hintText: 'e.g. Hall A'),
          textInputAction: TextInputAction.done,
        ),
        const SizedBox(height: Space.xl),
        Row(
          children: [
            Expanded(
              child: OutlinedButton(
                onPressed: () => Navigator.pop(
                  context,
                  DashboardFilters(dateFrom: widget.initial.dateFrom, dateTo: widget.initial.dateTo),
                ),
                child: const Text('Clear'),
              ),
            ),
            const SizedBox(width: Space.md),
            Expanded(
              child: FilledButton(onPressed: () => Navigator.pop(context, _result()), child: const Text('Apply')),
            ),
          ],
        ),
      ],
    );
  }
}
