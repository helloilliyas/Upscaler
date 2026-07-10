import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:intl/intl.dart';
import 'package:share_plus/share_plus.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../api_client.dart';
import '../history.dart';
import '../widgets/before_after.dart';
import 'settings_screen.dart';

class ResultScreen extends StatefulWidget {
  final HistoryEntry entry;
  const ResultScreen({super.key, required this.entry});

  @override
  State<ResultScreen> createState() => _ResultScreenState();
}

class _ResultScreenState extends State<ResultScreen> {
  HistoryEntry get entry => widget.entry;
  bool _refining = false;

  Future<void> _refine() async {
    setState(() => _refining = true);
    final messenger = ScaffoldMessenger.of(context);
    try {
      final prefs = await SharedPreferences.getInstance();
      final key = prefs.getString(kAnthropicKeyPref);
      final result = await VectorApi().refine(
        File(entry.inputPath),
        preset: entry.preset.replaceAll(' +AI', ''),
        anthropicKey: key,
      );
      final refined = await HistoryStore.add(
        input: File(entry.inputPath),
        output: result.svgBytes,
        preset: '${entry.preset.replaceAll(' +AI', '')} +AI',
        format: 'svg',
        pathCount: result.pathCount,
      );
      if (!mounted) return;
      await Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => ResultScreen(entry: refined)));
      messenger.showSnackBar(SnackBar(
        content: Text(result.aiNotes == null || result.aiNotes!.isEmpty
            ? 'Refined (score ${result.scoreBaseline.toStringAsFixed(1)} \u2192 ${result.scoreFinal.toStringAsFixed(1)})'
            : 'AI: ${result.aiNotes}'),
        duration: const Duration(seconds: 6),
        behavior: SnackBarBehavior.floating,
      ));
    } catch (e) {
      messenger.showSnackBar(SnackBar(
        content: Text(e.toString()),
        behavior: SnackBarBehavior.floating,
      ));
    } finally {
      if (mounted) setState(() => _refining = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('${entry.preset} · ${entry.format.toUpperCase()}'),
        actions: [
          IconButton(
            tooltip: 'Delete',
            icon: const Icon(Icons.delete_outline),
            onPressed: () async {
              await HistoryStore.remove(entry);
              if (context.mounted) Navigator.of(context).pop(true);
            },
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: Container(
              margin: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(12),
                border: Border.all(
                    color: Theme.of(context).colorScheme.outlineVariant),
              ),
              clipBehavior: Clip.antiAlias,
              child: _preview(context),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
            child: Text(
              '${entry.pathCount} paths · '
              '${DateFormat('d MMM y, HH:mm').format(entry.date)}\n'
              '${entry.downloadsName != null ? 'In Downloads as ${entry.downloadsName}' : 'Saved in app · use Share to export'}',
              style: Theme.of(context).textTheme.bodySmall,
              textAlign: TextAlign.center,
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
            child: Row(
              children: [
                if (entry.format == 'svg') ...[
                  Expanded(
                    child: OutlinedButton.icon(
                      icon: _refining
                          ? const SizedBox(
                              width: 16,
                              height: 16,
                              child: CircularProgressIndicator(strokeWidth: 2))
                          : const Icon(Icons.auto_awesome),
                      label: Text(_refining ? 'Refining\u2026' : 'Refine with AI'),
                      onPressed: _refining ? null : _refine,
                    ),
                  ),
                  const SizedBox(width: 10),
                ],
                Expanded(
                  child: FilledButton.icon(
                    icon: const Icon(Icons.share),
                    label: const Text('Share / Export'),
                    onPressed: () => Share.shareXFiles(
                      [XFile(entry.outputPath)],
                      text: 'Vectorized with my converter',
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _preview(BuildContext context) {
    final before = Image.file(File(entry.inputPath), fit: BoxFit.contain);
    switch (entry.format) {
      case 'svg':
        return FutureBuilder<String>(
          future: File(entry.outputPath).readAsString(),
          builder: (context, snap) {
            if (!snap.hasData) {
              return const Center(child: CircularProgressIndicator());
            }
            return BeforeAfter(
              before: before,
              after: Container(
                color: Colors.white,
                child: SvgPicture.string(snap.data!, fit: BoxFit.contain),
              ),
            );
          },
        );
      case 'png':
        return BeforeAfter(
          before: before,
          after: Container(
            color: Colors.white,
            child:
                Image.file(File(entry.outputPath), fit: BoxFit.contain),
          ),
        );
      default: // pdf — no inline preview
        return Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.picture_as_pdf_outlined, size: 72),
              const SizedBox(height: 12),
              Text('PDF saved',
                  style: Theme.of(context).textTheme.titleMedium),
              const Text('Use Share to open it in a PDF viewer'),
            ],
          ),
        );
    }
  }
}
