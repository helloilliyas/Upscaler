import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

const kAnthropicKeyPref = 'anthropic_api_key';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _controller = TextEditingController();
  bool _obscure = true;
  bool _hasKey = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final prefs = await SharedPreferences.getInstance();
    final key = prefs.getString(kAnthropicKeyPref) ?? '';
    if (!mounted) return;
    setState(() {
      _controller.text = key;
      _hasKey = key.isNotEmpty;
    });
  }

  Future<void> _save() async {
    final prefs = await SharedPreferences.getInstance();
    final key = _controller.text.trim();
    if (key.isEmpty) {
      await prefs.remove(kAnthropicKeyPref);
    } else {
      await prefs.setString(kAnthropicKeyPref, key);
    }
    if (!mounted) return;
    setState(() => _hasKey = key.isNotEmpty);
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(key.isEmpty ? 'API key removed' : 'API key saved'),
      behavior: SnackBarBehavior.floating,
    ));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('Anthropic API key',
              style: Theme.of(context).textTheme.titleSmall),
          const SizedBox(height: 6),
          const Text(
            'Used only by "Refine with AI" — Claude visually compares your '
            'result with the original and corrects colors. The key is stored '
            'on this phone and sent only with refine requests; the server '
            'never saves it. Get one at console.anthropic.com.',
            style: TextStyle(fontSize: 13),
          ),
          const SizedBox(height: 14),
          TextField(
            controller: _controller,
            obscureText: _obscure,
            autocorrect: false,
            enableSuggestions: false,
            decoration: InputDecoration(
              border: const OutlineInputBorder(),
              hintText: 'sk-ant-...',
              suffixIcon: IconButton(
                icon: Icon(_obscure ? Icons.visibility : Icons.visibility_off),
                onPressed: () => setState(() => _obscure = !_obscure),
              ),
            ),
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              FilledButton(onPressed: _save, child: const Text('Save')),
              const SizedBox(width: 12),
              if (_hasKey)
                OutlinedButton(
                  onPressed: () {
                    _controller.clear();
                    _save();
                  },
                  child: const Text('Remove key'),
                ),
            ],
          ),
          const SizedBox(height: 20),
          Text(
            _hasKey
                ? 'Refine with AI runs at full strength (measured search + '
                    'Claude vision critique).'
                : 'Without a key, Refine with AI still works using the '
                    'measured search only.',
            style: Theme.of(context)
                .textTheme
                .bodySmall
                ?.copyWith(fontStyle: FontStyle.italic),
          ),
        ],
      ),
    );
  }
}
