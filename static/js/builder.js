/* 组卷工作台：勾选加题、原生 HTML5 拖拽排序（支持跨板块）、分值实时统计。 */

(function () {
  'use strict';

  const cfgEl = document.getElementById('paper-config');
  if (!cfgEl) return;
  const cfg = JSON.parse(cfgEl.textContent);
  const urls = cfg.urls;

  const sectionUpdateBase = urls.sectionUpdate.replace('/0/', '/');
  const sectionDeleteBase = urls.sectionDelete.replace('/0/', '/');
  const itemUpdateBase = urls.update.replace('/0/', '/');
  const itemRemoveBase = urls.remove.replace('/0/', '/');

  /* ---------------------------------------------------- 选中计数 */
  const checkboxes = Array.from(document.querySelectorAll('.q-check'));
  const checkedCount = document.getElementById('checked-count');

  function refreshChecked() {
    const count = checkboxes.filter((c) => c.checked).length;
    if (checkedCount) checkedCount.textContent = String(count);
  }
  checkboxes.forEach((c) => c.addEventListener('change', refreshChecked));

  document.getElementById('btn-add').addEventListener('click', async () => {
    const ids = checkboxes.filter((c) => c.checked).map((c) => c.value);
    if (!ids.length) {
      window.toast('请先勾选要加入的题目', 'warning');
      return;
    }
    const { data } = await window.api(urls.add, { body: { question_ids: ids } });
    if (data.ok) {
      window.toast(`已加入 ${data.added} 题${data.skipped && data.skipped.length ? `，跳过重复 ${data.skipped.length} 题` : ''}`, 'success');
      setTimeout(() => location.reload(), 600);
    } else {
      window.toast(data.error || '加入失败', 'error');
    }
  });

  /* ---------------------------------------------------- 移除题目 */
  document.querySelectorAll('.js-remove').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const itemId = btn.dataset.itemId;
      const node = btn.closest('.q-item');
      const { data } = await window.api(itemRemoveBase + itemId + '/', {});
      if (data.ok) {
        node.remove();
        recalc();
        window.toast('已移除', 'success');
      } else {
        window.toast(data.error || '移除失败', 'error');
      }
    });
  });

  /* ---------------------------------------------------- 改分值 */
  const pointsInputs = Array.from(document.querySelectorAll('.js-points'));
  pointsInputs.forEach((input) => {
    let timer = null;
    input.addEventListener('input', () => {
      clearTimeout(timer);
      timer = setTimeout(async () => {
        const itemId = input.dataset.itemId;
        const { data } = await window.api(itemUpdateBase + itemId + '/', {
          body: { points: input.value }
        });
        if (data.ok) {
          recalc();
        } else {
          window.toast(data.error || '保存失败', 'error');
        }
      }, 400);
    });
  });

  function recalc() {
    let total = 0;
    document.querySelectorAll('.js-points').forEach((i) => {
      total += parseFloat(i.value || '0') || 0;
    });
    total = Math.round(total * 100) / 100;
    const items = document.querySelectorAll('#paper-panel .q-item').length;
    const sections = document.querySelectorAll('#paper-panel .section-block').length;

    const statTotal = document.getElementById('stat-total');
    const statTotal2 = document.getElementById('stat-total2');
    const statCount = document.getElementById('stat-count');
    const statSections = document.getElementById('stat-sections');
    const statGap = document.getElementById('stat-gap');
    if (statTotal) statTotal.textContent = String(total);
    if (statTotal2) statTotal2.textContent = String(total);
    if (statCount) statCount.textContent = String(items);
    if (statSections) statSections.textContent = String(sections);

    const target = parseFloat((document.getElementById('score-bar') || {}).dataset
      ? (document.getElementById('score-bar').dataset.target || '0') : '0');
    if (target && statGap) {
      const gap = Math.round((target - total) * 100) / 100;
      statGap.textContent = String(gap);
      statGap.className = 'v ' + (gap === 0 ? 'ok' : 'warn');
    }
    if (statTotal) statTotal.className = 'v ' + (statGap && String(statGap.textContent) === '0' ? 'ok' : 'warn');
  }

  /* ---------------------------------------------------- 拖拽排序 */
  let draggedItem = null;

  document.addEventListener('dragstart', (event) => {
    const item = event.target.closest('.q-item[data-item-id]');
    if (!item) return;
    draggedItem = item;
    event.dataTransfer.effectAllowed = 'move';
    setTimeout(() => item.classList.add('dragging'), 0);
  });

  document.addEventListener('dragend', () => {
    if (draggedItem) draggedItem.classList.remove('dragging');
    draggedItem = null;
    document.querySelectorAll('.section-body').forEach((s) => s.classList.remove('dragover'));
  });

  document.querySelectorAll('.section-body').forEach((body) => {
    body.addEventListener('dragover', (event) => {
      event.preventDefault();
      event.dataTransfer.dropEffect = 'move';
      body.classList.add('dragover');
    });
    body.addEventListener('dragleave', (event) => {
      if (!body.contains(event.relatedTarget)) body.classList.remove('dragover');
    });
    body.addEventListener('drop', (event) => {
      event.preventDefault();
      body.classList.remove('dragover');
      if (!draggedItem) return;

      const emptyHint = body.querySelector('.dropzone-empty');
      if (emptyHint) emptyHint.remove();

      // 放到鼠标位置最近的元素之前，简单可靠
      const reference = [...body.querySelectorAll('.q-item')].find((el) => {
        const rect = el.getBoundingClientRect();
        return event.clientY < rect.top + rect.height / 2;
      });
      if (reference) body.insertBefore(draggedItem, reference);
      else body.appendChild(draggedItem);

      saveOrder();
    });
  });

  async function saveOrder() {
    const orders = [];
    document.querySelectorAll('#paper-panel .section-block').forEach((block) => {
      const sectionId = block.querySelector('.section-body').dataset.sectionId;
      block.querySelectorAll('.q-item[data-item-id]').forEach((item, index) => {
        orders.push({
          item_id: Number(item.dataset.itemId),
          section_id: Number(sectionId),
          order: index + 1
        });
      });
    });
    if (!orders.length) return;
    const { data } = await window.api(urls.reorder, { body: { orders: orders } });
    if (!data.ok) window.toast(data.error || '顺序保存失败', 'error');
    else renumber();
  }

  function renumber() {
    document.querySelectorAll('#paper-panel .section-block').forEach((block) => {
      block.querySelectorAll('.q-item[data-item-id]').forEach((item, index) => {
        const stem = item.querySelector('.q-stem b');
        if (stem) stem.textContent = (index + 1) + '.';
      });
    });
  }

  /* ---------------------------------------------------- 板块操作 */
  const newSectionBtn = document.getElementById('btn-new-section');
  if (newSectionBtn) {
    newSectionBtn.addEventListener('click', async () => {
      const title = prompt('新板块名称，例如：阅读理解', '新板块');
      if (!title) return;
      const { data } = await window.api(urls.sectionCreate, {
        body: { title: title, section_type: 'custom', points_each: '1' }
      });
      if (data.ok) location.reload();
      else window.toast(data.error || '创建失败', 'error');
    });
  }

  document.querySelectorAll('.js-del-section').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const sectionId = btn.dataset.sectionId;
      if (!confirm('确定删除这个板块？板块里的题目会一并移出试卷。')) return;
      const { data } = await window.api(sectionDeleteBase + sectionId + '/', {});
      if (data.ok) location.reload();
      else window.toast(data.error || '删除失败', 'error');
    });
  });

  recalc();
})();
