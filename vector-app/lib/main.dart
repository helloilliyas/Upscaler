import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:intl/intl.dart';

import 'history.dart';
import 'screens/convert_screen.dart';
import 'screens/result_screen.dart';

void main() => runApp(const VectorApp());

class VectorApp extends StatelessWidget {
  const VectorApp({super.key});

  @override
  Widget build(BuildContext context) {
    const seed = Color(0xFF0F766E);
    return MaterialApp(
      title: 'Vectorizer',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(colorSchemeSeed: seed, useMaterial3: true),
      darkTheme: ThemeData(
          colorSchemeSeed: seed,
          brightness: Brightness.dark,
          useMaterial3: true),
      home: const HomeScreen(),
    );
  }
}

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final _picker = ImagePicker();
  List<HistoryEntry> _history = [];

  @override
  void initState() {
    super.initState();
    _reload();
  }

  Future<void> _reload() async {
    final h = await HistoryStore.load();
    if (mounted) setState(() => _history = h);
  }

  Future<void> _pick(ImageSource source) async {
    // Resize on-device before upload: faster on mobile data, smaller GPU bill.
    final picked = await _picker.pickImage(
      source: source,
      maxWidth: 2048,
      maxHeight: 2048,
      imageQuality: 92,
    );
    if (picked == null || !mounted) return;
    await Navigator.of(context).push(MaterialPageRoute(
        builder: (_) => ConvertScreen(image: File(picked.path))));
    _reload();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Vectorizer')),
      body: _history.isEmpty ? _empty(context) : _grid(),
      floatingActionButton: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          FloatingActionButton.small(
            heroTag: 'camera',
            tooltip: 'Camera',
            onPressed: () => _pick(ImageSource.camera),
            child: const Icon(Icons.photo_camera_outlined),
          ),
          const SizedBox(height: 12),
          FloatingActionButton.extended(
            heroTag: 'gallery',
            onPressed: () => _pick(ImageSource.gallery),
            icon: const Icon(Icons.add_photo_alternate_outlined),
            label: const Text('Convert image'),
          ),
        ],
      ),
    );
  }

  Widget _empty(BuildContext context) => Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.gesture,
                size: 72, color: Theme.of(context).colorScheme.outline),
            const SizedBox(height: 16),
            Text('No conversions yet',
                style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 4),
            const Text('Pick an image to turn it into vectors'),
          ],
        ),
      );

  Widget _grid() => GridView.builder(
        padding: const EdgeInsets.fromLTRB(12, 12, 12, 96),
        gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
          crossAxisCount: 2,
          mainAxisSpacing: 12,
          crossAxisSpacing: 12,
          childAspectRatio: 0.82,
        ),
        itemCount: _history.length,
        itemBuilder: (context, i) {
          final e = _history[i];
          return Card(
            clipBehavior: Clip.antiAlias,
            child: InkWell(
              onTap: () async {
                await Navigator.of(context).push(MaterialPageRoute(
                    builder: (_) => ResultScreen(entry: e)));
                _reload();
              },
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Expanded(
                      child:
                          Image.file(File(e.inputPath), fit: BoxFit.cover)),
                  Padding(
                    padding: const EdgeInsets.all(10),
                    child: Row(
                      children: [
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(e.preset,
                                  style: Theme.of(context)
                                      .textTheme
                                      .titleSmall),
                              Text(DateFormat('d MMM, HH:mm').format(e.date),
                                  style: Theme.of(context)
                                      .textTheme
                                      .bodySmall),
                            ],
                          ),
                        ),
                        Chip(
                          label: Text(e.format.toUpperCase(),
                              style: const TextStyle(fontSize: 10)),
                          padding: EdgeInsets.zero,
                          visualDensity: VisualDensity.compact,
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          );
        },
      );
}
