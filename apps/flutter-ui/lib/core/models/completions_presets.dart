import 'package:flutter/material.dart';

class CompletionsProviderPreset {
  const CompletionsProviderPreset({
    required this.id,
    required this.name,
    required this.icon,
    required this.url,
    this.defaultModel,
    this.knownModels,
  });
  final String id;
  final String name;
  final IconData icon;
  final String url;
  final String? defaultModel;
  final List<String>? knownModels;
}

class CompletionsProviderPresets {
  static const openai = CompletionsProviderPreset(
    id: 'openai',
    name: 'OpenAI',
    icon: Icons.auto_awesome,
    url: 'https://api.openai.com/v1',
    defaultModel: 'gpt-4-turbo',
    knownModels: ['gpt-4-turbo', 'gpt-4', 'gpt-3.5-turbo'],
  );

  static const anthropic = CompletionsProviderPreset(
    id: 'anthropic',
    name: 'Anthropic',
    icon: Icons.psychology,
    url: 'https://api.anthropic.com/v1',
    defaultModel: 'claude-3-opus-20240229',
    knownModels: ['claude-3-opus-20240229', 'claude-3-sonnet-20240229'],
  );

  static const ollama = CompletionsProviderPreset(
    id: 'ollama',
    name: 'Ollama (Local)',
    icon: Icons.computer,
    url: 'http://localhost:11434/v1',
    defaultModel: 'llama3',
  );

  static const lmStudio = CompletionsProviderPreset(
    id: 'lm_studio',
    name: 'LM Studio (Local)',
    icon: Icons.desktop_windows,
    url: 'http://localhost:1234/v1',
  );

  static const List<CompletionsProviderPreset> all = [
    openai,
    anthropic,
    ollama,
    lmStudio,
  ];

  static CompletionsProviderPreset? byUrl(String url) {
    try {
      return all.firstWhere((p) => url.startsWith(p.url));
    } on Object catch (_) {
      return null;
    }
  }
}
