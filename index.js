// 这是访问密钥
const SECRET_PASS = "123456";

export default {
  async fetch(request, env) {
    if (request.method !== 'POST') {
      return new Response('Only POST requests are allowed', { status: 405 });
    }

    const body = await request.json();
    let text = body.text;
    let source_language = body.source_language;
    let target_language = body.target_language;
    let secret = body.secret;

    if (secret !== SECRET_PASS) {
      return Response.json({
        code: 1,
        msg: "无权访问",
        text: null,
        source_language: null,
        target_language: null,
        secret: null
      });
    }

    const inputs = {
      text: text,
      source_lang: source_language.substr(0, 2),
      target_lang: target_language.substr(0, 2),
    };

    try {
      const response = await env.AI.run('@cf/meta/m2m100-1.2b', inputs);

      if (response.translated_text.indexOf('ERROR') === 0) {
        return Response.json({ code: 2, msg: "翻译错误", text: response.translated_text });
      }
      return Response.json({ code: 0, msg: "ok", text: response.translated_text });
    } catch (error) {
      return Response.json({ code: 3, msg: "内部错误", text: error.message });
    }
  },
};
