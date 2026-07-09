import 'dart:io';

import 'package:flutter/material.dart';

import '../api_client.dart';
import '../history.dart';
import 'result_screen.dart';

const presets = {
  'photo': ('Photo', Icons.photo_outlined, 'Natural photos, smooth curves'),
  'poster': ('Poster', Icons.palette_outlined, 'Flat art, reduced palette'),
  'logo': ('Logo', Icons.hexagon_outlined, 'Few colors, crisp edges'),
  'sketch': ('Sketch', Icons.draw_outlined, 'Black & white line art'),
};

class ConvertScreen extends StatefulWidget {
  final File image;
  const ConvertScreen({super.key, required this.image});

  @override
  State<ConvertScreen> createState() => _ConvertScreenState();
}

class _ConvertScreenState extends State<ConvertScreen> {
  final _api = VectorApi();

  String _preset = 'photo';
  double _colors = 8;
  bool _customColors = false;
  double _detail = 60;
  String _format = 'svg';

  bool _busy = false;
  double? _uploadProgress;

  Future<void> _convert() async {
    setState(() {
      _busy = true;
      _uploadProgress = 0;
    });
    try {
      final result = await _api.vectorize(
        widget.image,
        preset: _preset,
        colors: _customColors && _preset != 'sketch' ? _colors.round() : 0,
        detail: _detail.round(),
        format: _format,
        onUploadProgress: (p) => setState(() => _uploadProgress = p),
      );
      final entry = await HistoryStore.add(
        input: widget.image,
        output: result.bytes,
        preset: _preset,
        format: result.format,
        pathCount: result.pathCount,
      );
      if (!mounted) return;
      await Navigator.of(context).pushReplacement(MaterialPageRoute(
          builder: (_) => ResultScreen(entry: entry)));
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(e.toString()),
        behavior: SnackBarBehavior.floating,
      ));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final sketch = _preset == 'sketch';
    return Scaffold(
      appBar: AppBar(title: const Text('Convert')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(12),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxHeight: 280),
              child: Image.file(widget.image, fit: BoxFit.contain),
            ),
          ),
          const SizedBox(height: 20),
          Text('Style', style: Theme.of(context).textTheme.titleSmall),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: presets.entries.map((e) {
              final (label, icon, _) = e.value;
              return ChoiceChip(
                avatar: Icon(icon, size: 18),
                label: Text(label),
                selected: _preset == e.key,
                onSelected: (_) => setState(() => _preset = e.key),
              );
            }).toList(),
          ),
          const SizedBox(height: 4),
          Text(presets[_preset]!.$3,
              style: Theme.of(context).textTheme.bodySmall),
          const SizedBox(height: 20),
          Row(
            children: [
              Text('Detail', style: Theme.of(context).textTheme.titleSmall),
              const Spacer(),
              Text('${_detail.round()}'),
            ],
          ),
          Slider(
            value: _detail,
            min: 0,
            max: 100,
            divisions: 20,
            onChanged: _busy ? null : (v) => setState(() => _detail = v),
          ),
          if (!sketch) ...[
            Row(
              children: [
                Text('Limit colors',
                    style: Theme.of(context).textTheme.titleSmall),
                const Spacer(),
                Switch(
                  value: _customColors,
                  onChanged: _busy
                      ? null
                      : (v) => setState(() => _customColors = v),
                ),
              ],
            ),
            if (_customColors)
              Row(
                children: [
                  Expanded(
                    child: Slider(
                      value: _colors,
                      min: 2,
                      max: 32,
                      divisions: 30,
                      onChanged:
                          _busy ? null : (v) => setState(() => _colors = v),
                    ),
                  ),
                  SizedBox(width: 32, child: Text('${_colors.round()}')),
                ],
              ),
          ],
          const SizedBox(height: 8),
          Text('Output', style: Theme.of(context).textTheme.titleSmall),
          const SizedBox(height: 8),
          SegmentedButton<String>(
            segments: const [
              ButtonSegment(value: 'svg', label: Text('SVG')),
              ButtonSegment(value: 'pdf', label: Text('PDF')),
              ButtonSegment(value: 'png', label: Text('PNG')),
            ],
            selected: {_format},
            onSelectionChanged:
                _busy ? null : (s) => setState(() => _format = s.first),
          ),
          const SizedBox(height: 28),
          FilledButton.icon(
            onPressed: _busy ? null : _convert,
            icon: _busy
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2))
                : const Icon(Icons.auto_fix_high),
            label: Text(_busy
                ? (_uploadProgress != null && _uploadProgress! < 1
                    ? 'Uploading ${(100 * _uploadProgress!).round()}%'
                    : 'Converting…')
                : 'Convert'),
            style: FilledButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: 16)),
          ),
        ],
      ),
    );
  }
}
