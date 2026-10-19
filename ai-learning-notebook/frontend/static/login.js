const loginForm = document.getElementById("loginForm");
const loginError = document.getElementById("loginError");
const loginButton = document.getElementById("loginButton");
const authToggle = document.getElementById("authToggle");
const authIntro = document.getElementById("authIntro");
const authPrompt = document.getElementById("authPrompt");
let creatingAccount = false;

authToggle.addEventListener("click", () => {
  creatingAccount = !creatingAccount;
  loginButton.textContent = creatingAccount ? "Create account" : "Sign in";
  document.getElementById("loginPassword").minLength = creatingAccount ? 12 : 1;
  document.getElementById("loginPassword").autocomplete = creatingAccount ? "new-password" : "current-password";
  authIntro.textContent = creatingAccount ? "Create your own private study workspace." : "Sign in to your private study workspace.";
  authPrompt.textContent = creatingAccount ? "Already have an account?" : "New to Subjectly?";
  authToggle.textContent = creatingAccount ? "Sign in" : "Create an account";
  loginError.hidden = true;
});

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  loginError.hidden = true;
  loginButton.disabled = true;
  loginButton.textContent = "Signing in…";

  try {
    const response = await fetch(creatingAccount ? "/auth/register" : "/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: document.getElementById("loginEmail").value.trim(),
        password: document.getElementById("loginPassword").value,
      }),
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.detail || "Could not sign in. Please try again.");
    window.location.assign("/");
  } catch (error) {
    loginError.textContent = error.message;
    loginError.hidden = false;
  } finally {
    loginButton.disabled = false;
    loginButton.textContent = creatingAccount ? "Create account" : "Sign in";
  }
});
