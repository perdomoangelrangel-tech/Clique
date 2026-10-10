(function () {
  try {
    var t = localStorage.getItem('clique-theme');
    if (!t) t = 'dark';
    document.documentElement.setAttribute('data-theme', t);
  } catch (e) { document.documentElement.setAttribute('data-theme', 'dark'); }
})();
