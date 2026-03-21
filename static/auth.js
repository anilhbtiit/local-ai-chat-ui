async function login() {
    let r = await fetch("/login", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        username: username.value,
        password: password.value
      })
    });
  
    if (!r.ok) {
      alert("Login failed");
      return;
    }
  
    let data = await r.json();
  
    localStorage.setItem("token", data.token);
  
    // ✅ force clean navigation
    window.location.href = "/";
  }