/* 全站基础 JS：CSRF、提示、轻量的 fetch 封装。 */

window.getCookie = function (name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
};

window.csrfToken = function () {
  return window.getCookie('csrftoken');
};

/* 统一处理 403 CSRF 与 JSON 解析失败 */
window.api = async function (url, options) {
  const { method = 'POST', body = {}, rawUrl = false } = options || {};
  let requestUrl = url;
  const init = {
    method: method,
    headers: { 'X-CSRFToken': window.csrfToken() },
    credentials: 'same-origin'
  };

  if (method !== 'GET') {
    init.headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(body);
  } else if (body && Object.keys(body).length) {
    const params = new URLSearchParams(body).toString();
    requestUrl = requestUrl + (requestUrl.includes('?') ? '&' : '?') + params;
  }

  const response = await fetch(requestUrl, init);
  const text = await response.text();
  let data;
  try {
    data = text ? JSON.parse(text) : {};
  } catch (e) {
    data = { ok: false, error: '服务端返回了非 JSON 内容' };
  }
  return { response: response, data: data };
};

window.toast = function (message, kind) {
  const el = document.createElement('div');
  el.className = 'alert alert-' + (kind || 'info');
  el.style.position = 'fixed';
  el.style.top = '16px';
  el.style.left = '50%';
  el.style.transform = 'translateX(-50%)';
  el.style.zIndex = '9999';
  el.style.boxShadow = '0 4px 16px rgba(0,0,0,.12)';
  el.textContent = message;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 2200);
};
