(function(){
  var KEY="ignite-sentinel:color-mode",root=document.documentElement,btn=document.getElementById("modeToggle");
  function save(value){try{window.localStorage.setItem(KEY,value)}catch(e){}}
  function current(){var v=root.getAttribute("data-theme");if(v==="light"||v==="dark")return v;return window.matchMedia&&window.matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light"}
  function label(){if(!btn)return;var dark=current()==="dark";btn.textContent=dark?btn.getAttribute("data-light"):btn.getAttribute("data-dark");btn.setAttribute("aria-pressed",dark?"true":"false")}
  label();
  if(btn)btn.addEventListener("click",function(){var next=current()==="dark"?"light":"dark";root.setAttribute("data-theme",next);save(next);label()});
  var burger=document.querySelector(".shell-burger"),side=document.getElementById("sidebar");
  function setOpen(open){if(!burger||!side)return;side.classList.toggle("open",open);burger.setAttribute("aria-expanded",open?"true":"false")}
  if(burger)burger.addEventListener("click",function(){setOpen(burger.getAttribute("aria-expanded")!=="true")});
  if(side)side.addEventListener("click",function(e){if(e.target.closest&&e.target.closest("a,button"))setOpen(false)});
  document.addEventListener("keydown",function(e){if(e.key==="Escape")setOpen(false)});
})();
