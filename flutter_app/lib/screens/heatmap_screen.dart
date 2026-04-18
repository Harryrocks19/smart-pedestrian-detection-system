import 'package:flutter/material.dart';
import 'package:cached_network_image/cached_network_image.dart';
import '../api_service.dart';

class HeatmapScreen extends StatefulWidget {
  const HeatmapScreen({super.key});
  @override
  State<HeatmapScreen> createState() => _HeatmapScreenState();
}

class _HeatmapScreenState extends State<HeatmapScreen> {
  List<dynamic> _snaps = [];
  String _heatmapUrl = '';
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _fetch();
  }

  Future<void> _fetch() async {
    try {
      final snaps = await ApiService.getSnapshots();
      setState(() {
        _snaps = snaps;
        _heatmapUrl = '${ApiService.heatmapUrl()}?t=${DateTime.now().millisecondsSinceEpoch}';
        _loading = false;
      });
    } catch (_) {
      setState(() { _loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    backgroundColor: const Color(0xFF0D1117),
    appBar: AppBar(
      backgroundColor: const Color(0xFF161B22),
      title: const Text('Heatmap & Snapshots', style: TextStyle(color: Colors.white)),
      actions: [
        IconButton(icon: const Icon(Icons.refresh, color: Colors.white), onPressed: _fetch)
      ],
    ),
    body: _loading
        ? const Center(child: CircularProgressIndicator())
        : SingleChildScrollView(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('Live Heatmap', style: TextStyle(color: Colors.white70, fontSize: 14, fontWeight: FontWeight.bold)),
                const SizedBox(height: 8),
                ClipRRect(
                  borderRadius: BorderRadius.circular(10),
                  child: CachedNetworkImage(
                    imageUrl: _heatmapUrl,
                    placeholder: (_, __) => Container(
                      height: 200, color: const Color(0xFF161B22),
                      child: const Center(child: CircularProgressIndicator()),
                    ),
                    errorWidget: (_, __, ___) => Container(
                      height: 200, color: const Color(0xFF161B22),
                      child: const Center(child: Text('Heatmap not available yet', style: TextStyle(color: Colors.white38))),
                    ),
                    fit: BoxFit.cover,
                    width: double.infinity,
                  ),
                ),
                const SizedBox(height: 20),
                const Text('Alert Snapshots', style: TextStyle(color: Colors.white70, fontSize: 14, fontWeight: FontWeight.bold)),
                const SizedBox(height: 8),
                _snaps.isEmpty
                    ? const Text('No snapshots yet', style: TextStyle(color: Colors.white38))
                    : GridView.builder(
                        shrinkWrap: true,
                        physics: const NeverScrollableScrollPhysics(),
                        gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                          crossAxisCount: 2, crossAxisSpacing: 8, mainAxisSpacing: 8),
                        itemCount: _snaps.length,
                        itemBuilder: (_, i) => ClipRRect(
                          borderRadius: BorderRadius.circular(8),
                          child: CachedNetworkImage(
                            imageUrl: ApiService.snapshotUrl(_snaps[i]),
                            fit: BoxFit.cover,
                            placeholder: (_, __) => Container(color: const Color(0xFF161B22)),
                            errorWidget: (_, __, ___) => Container(
                              color: const Color(0xFF161B22),
                              child: const Icon(Icons.broken_image, color: Colors.white38),
                            ),
                          ),
                        ),
                      ),
              ],
            ),
          ),
  );
}
