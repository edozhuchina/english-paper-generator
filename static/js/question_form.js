/* 录题表单：按题型切换结构化录入面板，实时把结果写进 content / answer 两个 JSON 字段。
   面板只是"脚手架"，真正的存储始终是统一的 JSON schema，保证导入、组卷、导出都走同一套结构。 */

(function () {
  'use strict';

  const panelHost = document.getElementById('structured-panel');
  const typeSelect = document.getElementById('id_question_type');
  const contentEl = document.getElementById('id_content');
  const answerEl = document.getElementById('id_answer');
  if (!panelHost || !typeSelect || !contentEl || !answerEl) return;

  // code -> renderer_key
  const rendererMap = JSON.parse(document.getElementById('renderer-map').textContent || '{}');

  let currentKey = '';

  function parseJSON(text, fallback) {
    try {
      return JSON.parse(text || '{}');
    } catch (e) {
      return fallback;
    }
  }

  const helpers = {
    el(tag, attrs, children) {
      const node = document.createElement(tag);
      Object.entries(attrs || {}).forEach(([k, v]) => {
        if (k === 'class') node.className = v;
        else if (k === 'text') node.textContent = v;
        else node.setAttribute(k, v);
      });
      (children || []).forEach((c) => node.appendChild(c));
      return node;
    },
    field(labelText, control, helpText) {
      const wrap = this.el('div', { class: 'field field-full' });
      wrap.appendChild(this.el('label', { text: labelText }));
      wrap.appendChild(control);
      if (helpText) wrap.appendChild(this.el('div', { class: 'help', text: helpText }));
      return wrap;
    },
    textarea(rows, value) {
      const t = this.el('textarea', { rows: String(rows) });
      t.value = value || '';
      return t;
    },
    input(value) {
      const i = this.el('input', { type: 'text' });
      i.value = value || '';
      return i;
    }
  };

  const panels = {
    /* ------------------------------------------------ 选择题 */
    choice: {
      read(content, answer) {
        const options = content.options || [];
        const letters = ['A', 'B', 'C', 'D', 'E', 'F'];
        const host = helpers.el('div', { class: 'form-grid' });

        const optsWrap = helpers.el('div', { class: 'field field-full' });
        optsWrap.appendChild(helpers.el('label', { text: '选项（每行一个，不要写 A. 前缀，系统会自动加）' }));
        const opts = helpers.textarea(5, options.map((o) => o.text).join('\n'));
        optsWrap.appendChild(opts);
        host.appendChild(optsWrap);

        const keyWrap = helpers.el('div', { class: 'field' });
        keyWrap.appendChild(helpers.el('label', { text: '正确答案' }));
        const key = helpers.input((answer.value || []).join(','));
        keyWrap.appendChild(key);
        keyWrap.appendChild(helpers.el('div', { class: 'help', text: '单选填一个字母，如 B' }));
        host.appendChild(keyWrap);

        const layoutWrap = helpers.el('div', { class: 'field' });
        layoutWrap.appendChild(helpers.el('label', { text: '选项排版' }));
        const layout = helpers.el('select', {});
        [
          ['vertical', '竖排'],
          ['horizontal', '横排'],
          ['grid2', '两列'],
          ['grid4', '四宫格']
        ].forEach(([v, label]) => {
          const o = helpers.el('option', { value: v, text: label });
          if ((content.layout || {}).options === v) o.selected = true;
          layout.appendChild(o);
        });
        layoutWrap.appendChild(layout);
        host.appendChild(layoutWrap);

        host.appendChild(helpers.el('div', { class: 'field field-full help', text: '选项的顺序就是卷面上的 A、B、C、D 顺序。' }));
        panelHost.appendChild(host);

        return () => {
          const lines = opts.value.split('\n').map((s) => s.trim()).filter(Boolean);
          return {
            content: {
              v: 1,
              options: lines.map((text, i) => ({ key: letters[i] || String(i + 1), text: text, image_id: null })),
              layout: { options: layout.value }
            },
            answer: {
              v: 1,
              type: 'single_choice',
              value: key.value.split(',').map((s) => s.trim()).filter(Boolean)
            }
          };
        };
      }
    },

    /* ------------------------------------------------ 填空类 */
    blanks: {
      read(content, answer) {
        const host = helpers.el('div', { class: 'form-grid' });

        const bank = helpers.el('div', { class: 'field field-full' });
        bank.appendChild(helpers.el('label', { text: '备选词库（每行一个词，选词填空题型用）' }));
        const bankInput = helpers.textarea(3, (content.word_bank || []).join('\n'));
        bank.appendChild(bankInput);
        host.appendChild(bank);

        const given = helpers.el('div', { class: 'field field-full' });
        given.appendChild(helpers.el('label', { text: '提示词原型（每行一个，适当形式填空用）' }));
        const givenInput = helpers.textarea(3, (content.blanks || []).map((b) => b.given || '').filter(Boolean).join('\n'));
        given.appendChild(givenInput);
        host.appendChild(given);

        const ans = helpers.el('div', { class: 'field field-full' });
        ans.appendChild(helpers.el('label', { text: '答案（每个空一行；同一空多个可接受答案用 / 分隔）' }));
        const ansInput = helpers.textarea(4, (answer.value || []).map((b) => (b.value || []).join(' / ')).join('\n'));
        ans.appendChild(ansInput);
        ans.appendChild(helpers.el('div', { class: 'help', text: '题干里用 ___ 表示空位，例如：She ___ (like) apples.' }));
        host.appendChild(ans);

        const dir = helpers.el('div', { class: 'field' });
        dir.appendChild(helpers.el('label', { text: '翻译方向' }));
        const dirSelect = helpers.el('select', {});
        [['', '不指定'], ['e2c', '英译汉'], ['c2e', '汉译英']].forEach(([v, label]) => {
          const o = helpers.el('option', { value: v, text: label });
          if (content.direction === v) o.selected = true;
          dirSelect.appendChild(o);
        });
        dir.appendChild(dirSelect);
        host.appendChild(dir);

        panelHost.appendChild(host);

        return () => {
          const blanks = [];
          ansInput.value.split('\n').map((s) => s.trim()).filter(Boolean)
            .forEach((line, i) => {
              blanks.push({ no: i + 1, value: line.split('/').map((s) => s.trim()).filter(Boolean) });
            });
          const wordBank = bankInput.value.split('\n').map((s) => s.trim()).filter(Boolean);
          const givens = givenInput.value.split('\n').map((s) => s.trim()).filter(Boolean);
          const next = { v: 1 };
          if (wordBank.length) next.word_bank = wordBank;
          if (givens.length) next.blanks = givens.map((g) => ({ given: g }));
          if (dirSelect.value) next.direction = dirSelect.value;
          return {
            content: next,
            answer: { v: 1, type: 'blanks', value: blanks }
          };
        };
      }
    },

    /* ------------------------------------------------ 判断 */
    judge: {
      read(content, answer) {
        const host = helpers.el('div', { class: 'form-grid' });
        const st = helpers.el('div', { class: 'field field-full' });
        st.appendChild(helpers.el('label', { text: '陈述句（每行一条）' }));
        const stInput = helpers.textarea(5, (content.statements || []).map((s) => s.text).join('\n'));
        st.appendChild(stInput);
        host.appendChild(st);

        const ans = helpers.el('div', { class: 'field field-full' });
        ans.appendChild(helpers.el('label', { text: '答案（每行一个：T 或 F，与陈述句一一对应）' }));
        const ansInput = helpers.textarea(3, (answer.value || []).map((v) => (v ? 'T' : 'F')).join('\n'));
        ans.appendChild(ansInput);
        host.appendChild(ans);

        panelHost.appendChild(host);

        return () => {
          const statements = stInput.value.split('\n').map((s) => s.trim()).filter(Boolean)
            .map((text, i) => ({ no: i + 1, text: text }));
          const values = ansInput.value.split('\n').map((s) => s.trim().toUpperCase()).filter(Boolean)
            .map((v) => v === 'T' || v === 'TRUE' || v === '√' || v === '对');
          return {
            content: { v: 1, statements: statements },
            answer: { v: 1, type: 'tf', value: values }
          };
        };
      }
    },

    /* ------------------------------------------------ 排序 */
    order: {
      read(content, answer) {
        const host = helpers.el('div', { class: 'form-grid' });
        const items = helpers.el('div', { class: 'field field-full' });
        items.appendChild(helpers.el('label', { text: '打乱后的句子（每行一句，卷面就按这个顺序展示）' }));
        const itemInput = helpers.textarea(5, (content.items || []).map((s) => s.text).join('\n'));
        items.appendChild(itemInput);
        host.appendChild(items);

        const ans = helpers.el('div', { class: 'field field-full' });
        ans.appendChild(helpers.el('label', { text: '正确顺序（数字，逗号分隔，如 3,1,4,2）' }));
        const ansInput = helpers.input((answer.value || []).join(','));
        ans.appendChild(ansInput);
        host.appendChild(ans);

        panelHost.appendChild(host);

        return () => {
          const list = itemInput.value.split('\n').map((s) => s.trim()).filter(Boolean)
            .map((text, i) => ({ i: i + 1, text: text }));
          const order = ansInput.value.split(',').map((s) => s.trim()).filter(Boolean).map(Number);
          return {
            content: { v: 1, items: list, shuffle: true },
            answer: { v: 1, type: 'order', value: order }
          };
        };
      }
    },

    /* ------------------------------------------------ 连词成句 */
    unscramble: {
      read(content, answer) {
        const host = helpers.el('div', { class: 'form-grid' });
        const words = helpers.el('div', { class: 'field field-full' });
        words.appendChild(helpers.el('label', { text: '打乱的词汇（空格分隔，保留标点）' }));
        const wInput = helpers.input((content.words || []).join(' '));
        words.appendChild(wInput);
        host.appendChild(words);

        const dist = helpers.el('div', { class: 'field' });
        dist.appendChild(helpers.el('label', { text: '干扰词（空格分隔，可选）' }));
        const dInput = helpers.input((content.distractors || []).join(' '));
        dist.appendChild(dInput);
        host.appendChild(dist);

        const ans = helpers.el('div', { class: 'field field-full' });
        ans.appendChild(helpers.el('label', { text: '正确句子（多个可接受答案用 / 分隔）' }));
        const ansInput = helpers.input((((answer.value || [])[0] || {}).value || []).join(' / '));
        ans.appendChild(ansInput);
        host.appendChild(ans);

        panelHost.appendChild(host);

        return () => {
          return {
            content: {
              v: 1,
              words: wInput.value.split(/\s+/).filter(Boolean),
              distractors: dInput.value.split(/\s+/).filter(Boolean),
              punct_included: true
            },
            answer: {
              v: 1,
              type: 'blanks',
              value: [{ no: 1, value: ansInput.value.split('/').map((s) => s.trim()).filter(Boolean) }]
            }
          };
        };
      }
    },

    /* ------------------------------------------------ 改写句子 */
    rewrite: {
      read(content, answer) {
        const host = helpers.el('div', { class: 'form-grid' });
        const src = helpers.el('div', { class: 'field field-full' });
        src.appendChild(helpers.el('label', { text: '原句' }));
        const srcInput = helpers.input(content.source || '');
        src.appendChild(srcInput);
        host.appendChild(src);

        const req = helpers.el('div', { class: 'field field-full' });
        req.appendChild(helpers.el('label', { text: '改写要求' }));
        const reqInput = helpers.input(content.requirement || '');
        req.appendChild(reqInput);
        host.appendChild(req);

        const ans = helpers.el('div', { class: 'field field-full' });
        ans.appendChild(helpers.el('label', { text: '答案句子（多个可接受答案用 / 分隔）' }));
        const ansInput = helpers.input((((answer.value || [])[0] || {}).value || []).join(' / '));
        ans.appendChild(ansInput);
        host.appendChild(ans);

        panelHost.appendChild(host);

        return () => ({
          content: { v: 1, source: srcInput.value, requirement: reqInput.value, keep_marker: true },
          answer: {
            v: 1,
            type: 'blanks',
            value: [{ no: 1, value: ansInput.value.split('/').map((s) => s.trim()).filter(Boolean) }]
          }
        });
      }
    },

    /* ------------------------------------------------ 情景对话 */
    dialogue: {
      read(content, answer) {
        const host = helpers.el('div', { class: 'form-grid' });
        const lines = helpers.el('div', { class: 'field field-full' });
        lines.appendChild(helpers.el('label', { text: '对话内容（每行一句，格式：说话人: 内容，空位写 ___）' }));
        const lineInput = helpers.textarea(
          6,
          (content.lines || []).map((l) => `${l.role}: ${l.text}`).join('\n')
        );
        lines.appendChild(lineInput);
        host.appendChild(lines);

        const pool = helpers.el('div', { class: 'field field-full' });
        pool.appendChild(helpers.el('label', { text: '备选句子（七选五用，每行一条，格式：A. 内容）' }));
        const poolInput = helpers.textarea(6, (content.pool || []).map((p) => `${p.key}. ${p.text}`).join('\n'));
        pool.appendChild(poolInput);
        host.appendChild(pool);

        const mode = helpers.el('div', { class: 'field' });
        mode.appendChild(helpers.el('label', { text: '补全方式' }));
        const modeSelect = helpers.el('select', {});
        [['open', '开放式补全'], ['7choose5', '七选五']].forEach(([v, label]) => {
          const o = helpers.el('option', { value: v, text: label });
          if (content.mode === v) o.selected = true;
          modeSelect.appendChild(o);
        });
        mode.appendChild(modeSelect);
        host.appendChild(mode);

        const ans = helpers.el('div', { class: 'field field-full' });
        ans.appendChild(helpers.el('label', { text: '答案（每个空一行，多个可接受答案用 / 分隔）' }));
        const ansInput = helpers.textarea(4, (answer.value || []).map((b) => (b.value || []).join(' / ')).join('\n'));
        ans.appendChild(ansInput);
        host.appendChild(ans);

        panelHost.appendChild(host);

        return () => {
          const list = lineInput.value.split('\n').map((s) => s.trim()).filter(Boolean).map((line, i) => {
            const idx = line.indexOf(':');
            const role = idx > 0 ? line.slice(0, idx).trim() : 'A';
            const text = idx > 0 ? line.slice(idx + 1).trim() : line;
            return { role: role, text: text, blank_no: i + 1 };
          });
          const poolList = poolInput.value.split('\n').map((s) => s.trim()).filter(Boolean).map((line) => {
            const m = line.match(/^([A-G])\s*[.、．]\s*(.*)$/);
            return m ? { key: m[1], text: m[2] } : { key: '', text: line };
          });
          const blanks = ansInput.value.split('\n').map((s) => s.trim()).filter(Boolean)
            .map((v, i) => ({ no: i + 1, value: v.split('/').map((s) => s.trim()).filter(Boolean) }));
          return {
            content: { v: 1, mode: modeSelect.value, roles: ['A', 'B'], lines: list, pool: poolList },
            answer: { v: 1, type: 'blanks', value: blanks }
          };
        };
      }
    },

    /* ------------------------------------------------ 写作 */
    writing: {
      read(content, answer) {
        const host = helpers.el('div', { class: 'form-grid' });
        const topic = helpers.el('div', { class: 'field field-full' });
        topic.appendChild(helpers.el('label', { text: '题目 / 主题' }));
        const topicInput = helpers.input(content.topic || '');
        topic.appendChild(topicInput);
        host.appendChild(topic);

        const prompts = helpers.el('div', { class: 'field field-full' });
        prompts.appendChild(helpers.el('label', { text: '写作提示（每行一条）' }));
        const promptInput = helpers.textarea(4, (content.prompts || []).join('\n'));
        prompts.appendChild(promptInput);
        host.appendChild(prompts);

        const minWords = helpers.el('div', { class: 'field' });
        minWords.appendChild(helpers.el('label', { text: '建议词数' }));
        const minInput = helpers.input(String(content.min_words || content.min_sentences || ''));
        minInput.setAttribute('type', 'number');
        minWords.appendChild(minInput);
        host.appendChild(minWords);

        const rubric = helpers.el('div', { class: 'field field-full' });
        rubric.appendChild(helpers.el('label', { text: '评分要点（每行一条，格式：要点 |分值）' }));
        const rubricInput = helpers.textarea(4, (answer.rubric || []).map((r) => `${r.point} |${r.score}`).join('\n'));
        rubric.appendChild(rubricInput);
        host.appendChild(rubric);

        const sample = helpers.el('div', { class: 'field field-full' });
        sample.appendChild(helpers.el('label', { text: '参考范文' }));
        const sampleInput = helpers.textarea(6, (answer.sample || []).join('\n'));
        sample.appendChild(sampleInput);
        host.appendChild(sample);

        panelHost.appendChild(host);

        return () => {
          const rubrics = rubricInput.value.split('\n').map((s) => s.trim()).filter(Boolean).map((line) => {
            const parts = line.split('|').map((s) => s.trim());
            return { point: parts[0] || '', score: Number(parts[1]) || 0 };
          });
          const next = { v: 1, topic: topicInput.value, prompts: promptInput.value.split('\n').map((s) => s.trim()).filter(Boolean) };
          if (minInput.value) {
            next.min_words = Number(minInput.value) || 0;
            next.min_sentences = next.min_words > 0 && next.min_words < 20 ? next.min_words : 0;
          }
          const isWritingEl = document.getElementById('id_question_type');
          const code = isWritingEl.options[isWritingEl.selectedIndex].textContent;
          if (code.indexOf('看图写话') >= 0) {
            delete next.min_words;
            if (minInput.value) next.min_sentences = Number(minInput.value) || 0;
          }
          return {
            content: next,
            answer: {
              v: 1,
              type: 'rubric',
              rubric: rubrics,
              sample: sampleInput.value.split('\n').map((s) => s.trim()).filter(Boolean)
            }
          };
        };
      }
    }
  };

  function buildPanel() {
    panelHost.innerHTML = '';
    const option = typeSelect.options[typeSelect.selectedIndex];
    const code = option ? option.value : '';
    const key = rendererMap[code] || 'generic';
    currentKey = key;

    const builder = panels[key];
    if (!builder) {
      const note = helpers.el('div', {
        class: 'alert alert-info',
        text: '该题型的专用录入面板尚未提供，请直接在下方「结构与答案 JSON」里填写。schema 见项目 fixtures/question_types.json。'
      });
      panelHost.appendChild(note);
      return;
    }

    const content = parseJSON(contentEl.value, {});
    const answer = parseJSON(answerEl.value, {});
    const collect = builder.read(content, answer);

    const onInput = () => {
      const result = collect();
      contentEl.value = JSON.stringify(result.content, null, 2);
      answerEl.value = JSON.stringify(result.answer, null, 2);
    };
    panelHost.addEventListener('input', onInput);
    panelHost.addEventListener('change', onInput);
  }

  typeSelect.addEventListener('change', buildPanel);
  if (typeSelect.value) buildPanel();

  // 提交前做一次 JSON 合法性检查
  const form = document.getElementById('question-form');
  if (form) {
    form.addEventListener('submit', (event) => {
      try {
        JSON.parse(contentEl.value || '{}');
        JSON.parse(answerEl.value || '{}');
      } catch (e) {
        event.preventDefault();
        alert('「结构与答案」的 JSON 格式有误：' + e.message);
      }
    });
  }
})();
