"""Server-rendered DexSato email OTP sign-in page."""

from __future__ import annotations


def render_product_login_page() -> str:
    """Render a focused two-step login without exposing provider credentials."""
    return """<!doctype html>
<html lang="en" data-theme="intel">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Sign in · DexSato</title>
  <link rel="icon" href="/favicon.ico">
  <style>
    :root{color-scheme:dark;--bg:#080b10;--panel:#0f151c;--panel2:#121b24;--line:#263342;--text:#eef4f8;--muted:#8798aa;--cyan:#4cf4d6;--risk:#ff647c}
    *{box-sizing:border-box}body{min-height:100vh;margin:0;display:grid;place-items:center;padding:24px;background-color:var(--bg);background-image:linear-gradient(rgba(76,244,214,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(76,244,214,.035) 1px,transparent 1px);background-size:42px 42px;color:var(--text);font-family:"Segoe UI",Arial,sans-serif}
    .auth-shell{width:min(100%,430px)}.brand{display:flex;align-items:center;justify-content:center;gap:10px;margin-bottom:18px;color:var(--text);text-decoration:none}.brand img{width:38px;height:38px}.brand strong{font-size:22px}.brand span{color:var(--muted);font:10px ui-monospace,monospace;letter-spacing:.1em}
    .card{padding:28px;border:1px solid var(--line);background:rgba(15,21,28,.96);box-shadow:0 24px 80px rgba(0,0,0,.34)}.kicker{color:var(--cyan);font:700 10px ui-monospace,monospace;letter-spacing:.12em}.card h1{margin:8px 0 7px;font-size:27px}.intro{margin:0 0 22px;color:var(--muted);font-size:13px;line-height:1.55}
    form{display:grid;gap:10px}label{color:#b8c5d1;font-size:12px;font-weight:650}input{width:100%;height:46px;padding:0 13px;border:1px solid var(--line);border-radius:4px;background:var(--panel2);color:var(--text);font:14px ui-monospace,monospace;outline:0}input:focus{border-color:var(--cyan);box-shadow:0 0 0 2px rgba(76,244,214,.12)}button{height:44px;border:1px solid var(--cyan);border-radius:4px;background:var(--cyan);color:#07100e;font-weight:800;cursor:pointer}button:disabled{cursor:not-allowed;opacity:.55}.secondary{background:transparent;color:var(--cyan)}.row{display:grid;grid-template-columns:1fr 1fr;gap:10px}.message{min-height:20px;margin:12px 0 0;color:var(--muted);font:11px/1.5 ui-monospace,monospace}.message.error{color:var(--risk)}[hidden]{display:none!important}.back{display:block;margin-top:16px;color:var(--muted);font-size:12px;text-align:center;text-decoration:none}.back:hover{color:var(--cyan)}
  </style>
</head>
<body>
  <main class="auth-shell">
    <a class="brand" href="/"><img src="/static/branding/dexsato-mark.png" alt=""><strong>dexsato</strong><span>DEX INTELLIGENCE</span></a>
    <section class="card" aria-labelledby="auth-title">
      <span class="kicker">PRODUCT ACCOUNT</span>
      <h1 id="auth-title">Sign in to DexSato</h1>
      <p class="intro">Use your email to receive a one-time sign-in code. No password is required.</p>
      <form id="email-step">
        <label for="auth-email">Email address</label>
        <input id="auth-email" name="email" type="email" maxlength="254" autocomplete="email" required>
        <button type="submit">Send sign-in code</button>
      </form>
      <form id="code-step" hidden>
        <label for="auth-code">One-time code</label>
        <input id="auth-code" name="code" type="text" maxlength="16" inputmode="numeric" pattern="[0-9]+" autocomplete="one-time-code" required>
        <button type="submit">Verify and continue</button>
        <div class="row"><button id="resend" class="secondary" type="button" disabled>Resend in 60s</button><button id="change-email" class="secondary" type="button">Change email</button></div>
      </form>
      <p id="auth-message" class="message" role="status" aria-live="polite"></p>
    </section>
    <a class="back" href="/">Back to market feed</a>
  </main>
  <script>
    (()=>{
      const emailStep=document.getElementById("email-step"),codeStep=document.getElementById("code-step"),email=document.getElementById("auth-email"),code=document.getElementById("auth-code"),message=document.getElementById("auth-message"),resend=document.getElementById("resend"),change=document.getElementById("change-email");let seconds=0,timer=null;
      const show=(text,error=false)=>{message.textContent=text;message.classList.toggle("error",error)};
      const post=async(url,payload)=>{const response=await fetch(url,{method:"POST",headers:{"content-type":"application/json"},credentials:"same-origin",body:JSON.stringify(payload)});let data={};try{data=await response.json()}catch(error){}if(!response.ok)throw new Error(data.detail||"Authentication is temporarily unavailable.");return data};
      const cooldown=()=>{window.clearInterval(timer);seconds=60;resend.disabled=true;resend.textContent="Resend in 60s";timer=window.setInterval(()=>{seconds-=1;if(seconds<=0){window.clearInterval(timer);resend.disabled=false;resend.textContent="Resend code"}else resend.textContent=`Resend in ${seconds}s`},1000)};
      const requestCode=async()=>{show("Sending code…");await post("/auth/otp/request",{email:email.value});emailStep.hidden=true;codeStep.hidden=false;code.focus();cooldown();show("If delivery is available, check your email for the sign-in code.")};
      emailStep.addEventListener("submit",async event=>{event.preventDefault();try{await requestCode()}catch(error){show(error.message,true)}});
      codeStep.addEventListener("submit",async event=>{event.preventDefault();show("Verifying code…");try{const result=await post("/auth/otp/verify",{email:email.value,code:code.value});window.location.assign(result.redirect||"/")}catch(error){show(error.message,true)}});
      resend.addEventListener("click",async()=>{try{await requestCode()}catch(error){show(error.message,true)}});
      change.addEventListener("click",()=>{window.clearInterval(timer);codeStep.hidden=true;emailStep.hidden=false;code.value="";show("");email.focus()});
    })();
  </script>
</body>
</html>"""
