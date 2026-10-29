import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../design/theme.dart';
import '../design/widgets.dart';
import '../features/cases/data/models.dart' show PageResult;

typedef PageLoader<T> = Future<PageResult<T>> Function(int page);

/// A paginated, pull-to-refresh list with loading, empty, error-with-retry
/// and "couldn't load more" states. Change [reloadKey] to reload from page 1.
class PagedList<T> extends StatefulWidget {
  const PagedList({
    super.key,
    required this.load,
    required this.itemBuilder,
    required this.empty,
    this.header,
    this.loadingMessage = 'Loading…',
    this.reloadKey,
    this.separated = true,
  });

  final PageLoader<T> load;
  final Widget Function(BuildContext context, T item, int index) itemBuilder;
  final Widget empty;
  final Widget Function(BuildContext context, int count)? header;
  final String loadingMessage;
  final Object? reloadKey;
  final bool separated;

  @override
  State<PagedList<T>> createState() => PagedListState<T>();
}

class PagedListState<T> extends State<PagedList<T>> {
  final _scroll = ScrollController();
  final items = <T>[];
  int _page = 0;
  int _count = 0;
  bool _hasNext = true;
  bool _loading = false;
  ApiException? _error;
  ApiException? _pageError;
  int _generation = 0;

  @override
  void initState() {
    super.initState();
    _scroll.addListener(() {
      if (_scroll.position.pixels > _scroll.position.maxScrollExtent - 300) _loadMore();
    });
    WidgetsBinding.instance.addPostFrameCallback((_) => reload());
  }

  @override
  void didUpdateWidget(covariant PagedList<T> oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.reloadKey != widget.reloadKey) reload();
  }

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  /// Replaces one item in place (e.g. after marking it read).
  void replace(int index, T item) => setState(() => items[index] = item);

  Future<void> reload() async {
    if (!mounted) return;
    setState(() {
      _generation++;
      items.clear();
      _page = 0;
      _count = 0;
      _hasNext = true;
      _loading = false;
      _error = null;
      _pageError = null;
    });
    await _loadMore();
  }

  Future<void> _loadMore() async {
    if (_loading || !_hasNext) return;
    final generation = _generation;
    setState(() {
      _loading = true;
      _pageError = null;
    });
    try {
      final result = await widget.load(_page + 1);
      if (!mounted || generation != _generation) return;
      setState(() {
        _page += 1;
        items.addAll(result.items);
        _count = result.count;
        _hasNext = result.hasNext;
      });
    } on ApiException catch (e) {
      if (!mounted || generation != _generation) return;
      setState(() => items.isEmpty ? _error = e : _pageError = e);
    } finally {
      if (mounted && generation == _generation) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_error != null && items.isEmpty) {
      return MessageView.error(message: _error!.message, onRetry: reload);
    }
    if (items.isEmpty && (_loading || _page == 0)) return LoadingView(message: widget.loadingMessage);

    final children = <Widget>[
      ?widget.header?.call(context, _count),
      if (items.isEmpty) widget.empty,
      for (var i = 0; i < items.length; i++) ...[
        widget.itemBuilder(context, items[i], i),
        if (widget.separated && i < items.length - 1) const Divider(height: 1),
      ],
      if (_loading)
        const Padding(padding: EdgeInsets.all(Space.lg), child: Center(child: CircularProgressIndicator())),
      if (_pageError != null)
        Padding(
          padding: const EdgeInsets.all(Space.lg),
          child: Column(
            children: [
              Text(_pageError!.message, textAlign: TextAlign.center),
              TextButton(onPressed: _loadMore, child: const Text('Try again')),
            ],
          ),
        ),
    ];
    return RefreshIndicator(
      onRefresh: reload,
      child: ListView(
        controller: _scroll,
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.only(bottom: Space.xxl),
        children: children,
      ),
    );
  }
}
