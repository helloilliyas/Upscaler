/// Live backend deployed via the Upscaler repo's vector-deploy.yml workflow.
/// The API key is derived (HMAC-SHA256) from the Modal token secret at deploy
/// time; rotate by deleting the `vector-converter-secret` in Modal and
/// re-running the workflow, then update this constant.
class Config {
  static const backendUrl =
      'https://helloilliyas--vector-converter-api.modal.run';
  static const apiKey =
      'cfa78ad463390ab1bc7c7df4a0f5197793ba8289bb5d177f13b587a4ad09a1a6';
}
