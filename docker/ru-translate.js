/*
 * ru-translate-injected — Russian layer for FreqUI.
 *
 * FreqUI ships English-only (no i18n, no locale files), so instead of forking
 * the app this script rewrites the rendered DOM: it maps English UI strings to
 * Russian and keeps watching for nodes the Vue app adds later.
 *
 * Injected into the bundled index.html at image build time by
 * docker/inject-ui-translation.py.
 */
(function () {
  'use strict';

  var DICT = {
    // --- управление ботом -------------------------------------------------
    'Start Trading': 'Запустить торговлю',
    'Stop Trading': 'Остановить торговлю',
    'Stop Trading - Also stops handling open trades.':
      'Остановить торговлю — открытые сделки тоже перестанут вестись',
    'Pause (StopBuy)': 'Пауза (не входить)',
    'Pause (StopBuy) - Freqtrade will continue to handle open trades, but will not enter new trades or increase position sizes.':
      'Пауза: бот продолжит вести открытые сделки, но не будет открывать новые',
    'Reload Config': 'Перезагрузить конфиг',
    'ForceExit all': 'Закрыть все сделки',
    'Force Entry': 'Ручная покупка',
    'Force Exit': 'Закрыть сделку',
    'Force exit': 'Закрыть сделку',
    'Forceexit': 'Закрыть',
    'Reload': 'Перезагрузить',
    'Start': 'Запустить',
    'Stop': 'Остановить',

    // --- левое меню -------------------------------------------------------
    'Dashboard': 'Панель',
    'Trade': 'Торговля',
    'Chart': 'График',
    'Logs': 'Логи',
    'Settings': 'Настройки',
    'Backtest': 'Бэктест',
    'Balance': 'Баланс',
    'Pairlist': 'Список пар',
    'Download Data': 'Загрузка данных',
    'Download data': 'Загрузка данных',

    // --- вход -------------------------------------------------------------
    'Login': 'Вход',
    'Logout': 'Выйти',
    'Username': 'Имя пользователя',
    'Password': 'Пароль',
    'Bot name': 'Название бота',
    'API URL': 'URL API',
    'Submit': 'Отправить',
    'Cancel': 'Отмена',
    'Reset': 'Сброс',
    'Save': 'Сохранить',
    'Delete': 'Удалить',
    'Close': 'Закрыть',
    'Confirm': 'Подтвердить',

    // --- таблицы сделок ---------------------------------------------------
    'Open Trades': 'Открытые сделки',
    'Closed Trades': 'Закрытые сделки',
    'Trade History': 'История сделок',
    'Trade history': 'История сделок',
    'Pair': 'Пара',
    'Amount': 'Количество',
    'Open rate': 'Цена входа',
    'Close rate': 'Цена выхода',
    'Current rate': 'Текущая цена',
    'Profit': 'Прибыль',
    'Profit %': 'Прибыль %',
    'Duration': 'Длительность',
    'Entry': 'Вход',
    'Exit': 'Выход',
    'Stake amount': 'Сумма сделки',
    'Total': 'Всего',
    'Total profit': 'Общая прибыль',
    'Available': 'Доступно',
    'Used': 'Использовано',
    'Win rate': 'Процент побед',
    'Wins': 'Прибыльных',
    'Losses': 'Убыточных',
    'Trades': 'Сделки',
    'Show': 'Показать',
    'Hide': 'Скрыть',
    'Timeframe': 'Таймфрейм',
    'Strategy': 'Стратегия',
    'Exchange': 'Биржа',
    'State': 'Состояние',
    'running': 'работает',
    'stopped': 'остановлен',
    'Loading': 'Загрузка',
    'Refresh': 'Обновить',
    'No data': 'Нет данных'
  };

  // Longest keys first so "Trade History" wins over "Trade".
  var KEYS = Object.keys(DICT).sort(function (a, b) { return b.length - a.length; });
  var RES = KEYS.map(function (k) {
    var esc = k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    try {
      // Lookarounds instead of \b: keys like "Profit %" end with a non-word
      // character, where a word boundary can never match.
      return new RegExp('(?<![\\w])' + esc + '(?![\\w])', 'g');
    } catch (e) {
      return new RegExp('\\b' + esc + '\\b', 'g');
    }
  });

  function translate(value) {
    if (!value || value.length > 300 || !/[A-Za-z]/.test(value)) { return value; }
    var out = value;
    for (var i = 0; i < KEYS.length; i++) {
      if (out.indexOf(KEYS[i]) !== -1) { out = out.replace(RES[i], DICT[KEYS[i]]); }
    }
    return out;
  }

  function doText(node) {
    var next = translate(node.nodeValue);
    if (next !== node.nodeValue) { node.nodeValue = next; }
  }

  var ATTRS = ['placeholder', 'title', 'aria-label', 'alt', 'label'];

  function walk(root) {
    if (!root) { return; }
    if (root.nodeType === 3) { doText(root); return; }
    if (root.nodeType !== 1) { return; }

    for (var a = 0; a < ATTRS.length; a++) {
      if (root.hasAttribute && root.hasAttribute(ATTRS[a])) {
        var v = root.getAttribute(ATTRS[a]);
        var t = translate(v);
        if (t !== v) { root.setAttribute(ATTRS[a], t); }
      }
    }
    if (root.tagName === 'INPUT') {
      var type = (root.getAttribute('type') || '').toLowerCase();
      if (type === 'submit' || type === 'button') {
        var val = root.value;
        var tv = translate(val);
        if (tv !== val) { root.value = tv; }
      }
    }

    for (var c = root.firstChild; c; c = c.nextSibling) { walk(c); }
  }

  function start() {
    walk(document.body);
    var pending = false;
    var observer = new MutationObserver(function (mutations) {
      if (pending) { return; }
      pending = true;
      // Let Vue finish its render pass before walking the new nodes.
      setTimeout(function () {
        pending = false;
        for (var i = 0; i < mutations.length; i++) {
          var m = mutations[i];
          if (m.type === 'characterData') { doText(m.target); }
          for (var j = 0; j < m.addedNodes.length; j++) { walk(m.addedNodes[j]); }
        }
      }, 0);
    });
    observer.observe(document.body, { subtree: true, childList: true, characterData: true });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
