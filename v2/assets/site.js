/* Dad's Bookshelf — behaviour. Edit here, then run build.py.
   The pages work without this file: every book is a real link to a real page.
   This adds search, filters, the slide-in panel and the share buttons. */
(function(){
  "use strict";
  var ROOT = new URL("..", document.currentScript.src).href;   // assets/site.js -> site root
  var $ = function(id){ return document.getElementById(id); };

  /* ---------- share buttons (book pages and the panel) ---------- */
  function wireShare(scope){
    var art = scope.querySelector(".book");
    if(!art) return;
    var url = art.dataset.url, title = art.dataset.title;
    var copy = art.querySelector("[data-copy]"), share = art.querySelector("[data-share]");
    if(copy) copy.addEventListener("click", function(){
      var ok = function(){
        copy.textContent = "Link copied"; copy.classList.add("done");
        setTimeout(function(){ copy.textContent = "Copy link"; copy.classList.remove("done"); }, 1800);
      };
      if(navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(ok, fallback);
      else fallback();
      function fallback(){
        var ta = document.createElement("textarea");
        ta.value = url; ta.style.position = "fixed"; ta.style.opacity = "0";
        document.body.appendChild(ta); ta.select();
        try{ document.execCommand("copy"); ok(); }catch(e){}
        document.body.removeChild(ta);
      }
    });
    if(share && navigator.share){
      share.hidden = false;
      share.addEventListener("click", function(){
        navigator.share({ title: title + " — Dad's Bookshelf", url: url }).catch(function(){});
      });
    }
  }
  wireShare(document);

  var list = $("books");
  if(!list) return;                       // a book page: nothing more to do

  /* ---------- home page ---------- */
  var items = Array.prototype.slice.call(list.children);
  var byId = {};
  items.forEach(function(li, i){ li._o = i; byId[li.dataset.id] = li; });
  var total = items.length;
  var q = $("q"), form = q.form;
  var sel = { theme: $("f-theme"), region: $("f-region"), type: $("f-type"), year: $("f-year"), min: $("f-min"), sort: $("f-sort") };
  var chk = { great: $("f-great"), africa: $("f-africa"), words: $("f-words") };
  var viewBtns = Array.prototype.slice.call(document.querySelectorAll(".views button"));
  var bars = Array.prototype.slice.call(document.querySelectorAll(".bar"));
  var state = { view: "greats", q: "", theme: "", region: "", type: "", year: "", min: "", sort: "recent", great: false, africa: false, words: false, book: "" };
  var KEYS = ["q","theme","region","type","year","min","great","africa","words"];
  var INDEX = null;                       // id -> [facts, words] (folded), loaded once

  function fold(s){
    var out = "";
    s = String(s).toLowerCase();
    for(var i = 0; i < s.length; i++){
      var c = s[i];
      if(c > "\u007f"){
        if(c === "’" || c === "‘") c = "'";
        else { var n = c.normalize("NFD"); c = n.length > 1 && n[0] <= "\u007f" ? n[0] : c; }
      }
      out += c;
    }
    return out;
  }
  function esc(s){ return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }

  fetch(ROOT + "search.json").then(function(r){ return r.json(); }).then(function(d){
    INDEX = {};
    Object.keys(d).forEach(function(id){ INDEX[id] = { facts: fold(d[id][0]), raw: d[id][1], words: fold(d[id][1]) }; });
    if(state.q) apply();
  }).catch(function(){});

  function filtered(){
    return KEYS.some(function(k){ return state[k]; });
  }

  function readURL(){
    var p = new URLSearchParams(location.search);
    state.q = p.get("q") || "";
    ["theme","region","type","year","min"].forEach(function(k){ state[k] = p.get(k) || ""; });
    ["great","africa","words"].forEach(function(k){ state[k] = p.get(k) === "1"; });
    state.sort = p.get("sort") || "recent";
    state.view = p.get("view") || (filtered() ? "all" : "greats");
    if(["greats","all","authors"].indexOf(state.view) < 0) state.view = "greats";
    state.book = p.get("book") || "";
    q.value = state.q;
    Object.keys(sel).forEach(function(k){ sel[k].value = state[k]; if(sel[k].value !== state[k]) state[k] = sel[k].value; });
    Object.keys(chk).forEach(function(k){ chk[k].checked = state[k]; });
  }
  function urlFor(){
    var p = new URLSearchParams();
    if(state.view !== "greats") p.set("view", state.view);
    KEYS.forEach(function(k){ if(state[k]) p.set(k, state[k] === true ? "1" : state[k]); });
    if(state.sort !== "recent") p.set("sort", state.sort);
    if(state.book) p.set("book", state.book);
    var s = p.toString();
    return location.pathname + (s ? "?" + s : "") ;
  }
  function writeURL(push){
    history[push ? "pushState" : "replaceState"](null, "", urlFor());
  }

  function matches(li, tokens){
    var d = li.dataset;
    if(state.theme && d.th !== state.theme) return false;
    if(state.region && d.rg !== state.region) return false;
    if(state.type && d.ty !== state.type) return false;
    if(state.year && d.y !== state.year) return false;
    if(state.min && +d.r < +state.min) return false;
    if(state.great && d.g === "0") return false;
    if(state.africa && d.af !== "1") return false;
    if(state.words && d.w !== "1") return false;
    if(tokens.length){
      var ix = INDEX && INDEX[d.id];
      var hay = ix ? ix.facts + " \u0001 " + ix.words : fold(li.textContent);
      for(var i = 0; i < tokens.length; i++) if(hay.indexOf(tokens[i]) < 0) return false;
    }
    return true;
  }

  /* When the search hit is inside the notes, show that line of his notes. */
  function snippet(li, tokens){
    var el = li.querySelector(".bk-snip"), quote = li.querySelector(".bk-quote");
    var ix = INDEX && INDEX[li.dataset.id];
    var hit = -1, tok = "";
    if(ix && tokens.length){
      for(var i = 0; i < tokens.length; i++){
        if(ix.facts.indexOf(tokens[i]) < 0){
          var at = ix.words.indexOf(tokens[i]);
          if(at >= 0 && ix.words.length === ix.raw.length){ hit = at; tok = tokens[i]; break; }
        }
      }
    }
    if(hit < 0){ el.hidden = true; if(quote) quote.hidden = false; return; }
    var raw = ix.raw, a = Math.max(0, hit - 60), b = Math.min(raw.length, hit + tok.length + 90);
    var s0 = raw.lastIndexOf("¶", hit), s1 = raw.indexOf("¶", hit);   // stay inside one passage
    if(s0 >= 0) a = Math.max(a, s0 + 2);
    if(s1 >= 0) b = Math.min(b, s1 - 1);
    if(a > 0 && s0 + 2 !== a){ var sp = raw.indexOf(" ", a); if(sp >= 0 && sp < hit) a = sp + 1; }
    if(b < raw.length){ var sp2 = raw.lastIndexOf(" ", b); if(sp2 > hit + tok.length) b = sp2; }
    el.innerHTML = (a > 0 && s0 + 2 !== a ? "…" : "") + esc(raw.slice(a, hit)) + "<mark>" + esc(raw.slice(hit, hit + tok.length)) +
                   "</mark>" + esc(raw.slice(hit + tok.length, b)) + (b < raw.length && s1 - 1 !== b ? "…" : "");
    el.hidden = false;
    if(quote) quote.hidden = true;
  }

  var SORTS = {
    recent: function(a,b){ return b.dataset.y - a.dataset.y || cmp(a.dataset.t, b.dataset.t); },
    oldest: function(a,b){ return a.dataset.y - b.dataset.y || cmp(a.dataset.t, b.dataset.t); },
    rating: function(a,b){ return b.dataset.r - a.dataset.r || (b.dataset.g !== "0") - (a.dataset.g !== "0") || b.dataset.y - a.dataset.y; },
    title:  function(a,b){ return cmp(a.dataset.t, b.dataset.t); },
    author: function(a,b){ return cmp(a.dataset.a, b.dataset.a) || cmp(a.dataset.t, b.dataset.t); },
    pub:    function(a,b){ return b.dataset.p - a.dataset.p || cmp(a.dataset.t, b.dataset.t); }
  };
  function cmp(x, y){ return x < y ? -1 : x > y ? 1 : 0; }

  function apply(){
    var v = state.view;
    viewBtns.forEach(function(b){ b.setAttribute("aria-pressed", String(b.dataset.view === v)); });
    $("hero").hidden = v !== "greats";
    $("numbers").hidden = v !== "all";
    $("numbers").classList.toggle("searching", !!state.q);
    $("filters").hidden = v !== "all";
    $("authors").hidden = v !== "authors";
    $("shelf").hidden = v === "authors";
    if(v === "authors") return;

    list.className = "books view-" + v;
    var tokens = v === "all" ? fold(state.q).split(/\s+/).filter(Boolean) : [];
    var shown = [];
    items.forEach(function(li){
      var ok = v === "greats" ? li.dataset.g !== "0" : matches(li, tokens);
      li.hidden = !ok;
      if(ok){ shown.push(li); if(v === "all") snippet(li, tokens); else snippet(li, []); }
    });
    shown.sort(v === "greats" ? function(a,b){ return a.dataset.g - b.dataset.g; } : (SORTS[state.sort] || SORTS.recent));
    var frag = document.createDocumentFragment();
    shown.forEach(function(li){ frag.appendChild(li); });
    list.appendChild(frag);

    $("empty").hidden = shown.length > 0;
    if(v === "all"){
      var f = filtered();
      $("count").textContent = f ? shown.length + " of " + total + " books" : "All " + total + " books";
      $("f-clear").hidden = !f;
      Object.keys(sel).forEach(function(k){ if(k !== "sort") sel[k].classList.toggle("on", !!state[k]); });
      bars.forEach(function(b){ b.setAttribute("aria-pressed", String(b.dataset.year === state.year)); });
      document.querySelectorAll(".theme-intro").forEach(function(p){ p.hidden = p.dataset.th !== state.theme; });
    }
  }

  function change(push){ writeURL(push); apply(); }
  function clearFilters(){
    KEYS.forEach(function(k){ state[k] = typeof state[k] === "boolean" ? false : ""; });
    q.value = "";
    Object.keys(sel).forEach(function(k){ if(k !== "sort") sel[k].value = ""; });
    Object.keys(chk).forEach(function(k){ chk[k].checked = false; });
  }

  viewBtns.forEach(function(b){
    b.addEventListener("click", function(){
      state.view = b.dataset.view;
      if(state.view !== "all") clearFilters();
      change(true);
      window.scrollTo(0, 0);
    });
  });
  var typing;
  q.addEventListener("input", function(){
    state.q = q.value.trim();
    if(state.q) state.view = "all";
    clearTimeout(typing);
    typing = setTimeout(function(){ change(false); }, 90);
  });
  form.addEventListener("submit", function(e){ e.preventDefault(); q.blur(); $("shelf").scrollIntoView(); });
  Object.keys(sel).forEach(function(k){
    sel[k].addEventListener("change", function(){ state[k] = sel[k].value; change(false); });
  });
  Object.keys(chk).forEach(function(k){
    chk[k].addEventListener("change", function(){ state[k] = chk[k].checked; change(false); });
  });
  bars.forEach(function(b){
    b.addEventListener("click", function(){
      state.year = state.year === b.dataset.year ? "" : b.dataset.year;
      sel.year.value = state.year;
      change(false);
    });
  });
  $("f-clear").addEventListener("click", function(){ clearFilters(); change(false); });
  $("empty-clear").addEventListener("click", function(){ clearFilters(); change(false); });
  document.addEventListener("keydown", function(e){
    if(e.key === "/" && !/^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName)){ e.preventDefault(); q.focus(); }
  });

  /* ---------- slide-in panel: shows the book's own page ---------- */
  var wrap = $("panel-wrap"), panel = $("panel"), lastFocus = null;

  function showPanel(id){
    var li = byId[id];
    if(!li){ hidePanel(); return; }
    var href = li.querySelector(".bk-link").href;
    if(wrap.hidden) lastFocus = document.activeElement;
    wrap.hidden = false;
    document.body.classList.add("locked");
    panel.innerHTML = '<p class="panel-load">Opening…</p>';
    panel.scrollTop = 0;
    fetch(href).then(function(r){ if(!r.ok) throw 0; return r.text(); }).then(function(text){
      var doc = new DOMParser().parseFromString(text, "text/html");
      var art = doc.getElementById("book");
      if(!art) throw 0;
      art.querySelectorAll("a[href]").forEach(function(a){
        a.setAttribute("href", new URL(a.getAttribute("href"), href).href);
      });
      panel.innerHTML = '<button type="button" class="panel-close">Close</button>';
      panel.appendChild(document.importNode(art, true));
      panel.querySelector(".panel-close").addEventListener("click", closePanel);
      wireShare(panel);
      panel.focus();
    }).catch(function(){ location.href = href; });
  }
  function hidePanel(){
    if(wrap.hidden) return;
    wrap.hidden = true;
    panel.innerHTML = "";
    document.body.classList.remove("locked");
    if(lastFocus && lastFocus.focus) lastFocus.focus();
  }
  function openBook(id){ state.book = String(id); writeURL(true); showPanel(state.book); }
  function closePanel(){ state.book = ""; writeURL(true); hidePanel(); }

  document.addEventListener("click", function(e){
    if(e.metaKey || e.ctrlKey || e.shiftKey || e.button) return;
    var a = e.target.closest("a");
    if(!a) return;
    var li = a.classList.contains("bk-link") ? a.closest(".bk") : null;
    var id = li ? li.dataset.id : a.dataset.id;
    if(id && byId[id]){ e.preventDefault(); openBook(id); return; }
    /* links inside the panel that point back at the shelf (author, theme, year chips) */
    if(panel.contains(a) && a.origin === location.origin && a.pathname === location.pathname){
      e.preventDefault();
      hidePanel();
      history.pushState(null, "", a.search || location.pathname);
      readURL(); apply();
      $("main").scrollIntoView();
    }
  });
  wrap.addEventListener("mousedown", function(e){ if(e.target === wrap) closePanel(); });
  document.addEventListener("keydown", function(e){
    if(e.key === "Escape" && !wrap.hidden) closePanel();
    if(e.key === "Tab" && !wrap.hidden){
      var f = panel.querySelectorAll("a[href], button:not([hidden])");
      if(!f.length) return;
      if(!panel.contains(document.activeElement)){ e.preventDefault(); f[0].focus(); }
      else if(e.shiftKey && document.activeElement === f[0]){ e.preventDefault(); f[f.length-1].focus(); }
      else if(!e.shiftKey && document.activeElement === f[f.length-1]){ e.preventDefault(); f[0].focus(); }
    }
  });
  window.addEventListener("popstate", function(){
    readURL(); apply();
    if(state.book) showPanel(state.book); else hidePanel();
  });

  readURL();
  if(window.matchMedia("(max-width:640px)").matches &&
     !KEYS.some(function(k){ return k !== "q" && state[k]; })) $("fdetails").open = false;
  apply();
  if(state.book) showPanel(state.book);
  if(location.hash === "#suggest" && window.openFeedback) window.openFeedback();
  else if(location.hash === "#suggest") window.addEventListener("load", function(){ if(window.openFeedback) window.openFeedback(); });
})();
