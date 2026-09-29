/* ============================================================
   IP-SAKTI — auth.js
   PROTOTYPE-ONLY AUTHENTICATION.
   Users and sessions are stored in the browser's localStorage.
   Passwords are stored in plain text for demo purposes only —
   this is NOT secure and must never be used in production.
   ============================================================ */

window.IPSAKTI = window.IPSAKTI || {};

(function (ns) {
  const USERS_KEY = 'ipsakti_users';
  const SESSION_KEY = 'ipsakti_session';

  // ---------- storage helpers ----------
  function getUsers() {
    try {
      return JSON.parse(localStorage.getItem(USERS_KEY)) || [];
    } catch (e) {
      return [];
    }
  }

  function saveUsers(users) {
    localStorage.setItem(USERS_KEY, JSON.stringify(users));
  }

  function setSession(user, remember) {
    const session = { name: user.name, email: user.email, remember: !!remember, loggedInAt: Date.now() };
    localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  }

  function getSession() {
    try {
      return JSON.parse(localStorage.getItem(SESSION_KEY));
    } catch (e) {
      return null;
    }
  }

  function clearSession() {
    localStorage.removeItem(SESSION_KEY);
  }

  function isValidEmail(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  }

  function showBanner(message, type) {
    const banner = document.getElementById('formBanner');
    if (!banner) return;
    banner.textContent = message;
    banner.className = 'form-banner show ' + type;
  }

  function setFieldError(fieldId, show) {
    const field = document.getElementById(fieldId);
    if (!field) return;
    field.classList.toggle('has-error', show);
  }

  function wirePasswordToggle(root) {
    (root || document).querySelectorAll('.toggle-pw').forEach((btn) => {
      btn.addEventListener('click', () => {
        const targetId = btn.getAttribute('data-target');
        const input = document.getElementById(targetId);
        if (!input) return;
        const isHidden = input.type === 'password';
        input.type = isHidden ? 'text' : 'password';
        btn.textContent = isHidden ? 'Hide' : 'Show';
      });
    });
  }

  // ---------- Login page ----------
  function initLoginPage() {
    wirePasswordToggle(document);

    const form = document.getElementById('loginForm');
    const forgotLink = document.getElementById('forgotLink');

    // Pre-fill remembered email if present
    const lastEmail = localStorage.getItem('ipsakti_last_email');
    if (lastEmail) document.getElementById('email').value = lastEmail;

    forgotLink.addEventListener('click', (e) => {
      e.preventDefault();
      showBanner('This is a prototype — password reset is not implemented. Try logging in with the account you created on the sign-up page.', 'error');
    });

    form.addEventListener('submit', (e) => {
      e.preventDefault();
      const email = document.getElementById('email').value.trim().toLowerCase();
      const password = document.getElementById('password').value;
      const remember = document.getElementById('remember').checked;

      let hasError = false;
      setFieldError('emailField', false);
      setFieldError('passwordField', false);

      if (!isValidEmail(email)) {
        setFieldError('emailField', true);
        hasError = true;
      }
      if (!password) {
        setFieldError('passwordField', true);
        hasError = true;
      }
      if (hasError) return;

      const users = getUsers();
      const user = users.find((u) => u.email === email);

      if (!user || user.password !== password) {
        showBanner('Email or password is incorrect. If you don\'t have an account yet, sign up first.', 'error');
        return;
      }

      if (remember) localStorage.setItem('ipsakti_last_email', email);
      else localStorage.removeItem('ipsakti_last_email');

      setSession(user, remember);
      showBanner('Logged in! Redirecting to your dashboard…', 'success');
      setTimeout(() => { window.location.href = 'dashboard.html'; }, 500);
    });
  }

  // ---------- Signup page ----------
  function initSignupPage() {
    wirePasswordToggle(document);

    const form = document.getElementById('signupForm');

    form.addEventListener('submit', (e) => {
      e.preventDefault();
      const name = document.getElementById('name').value.trim();
      const email = document.getElementById('email').value.trim().toLowerCase();
      const password = document.getElementById('password').value;
      const confirm = document.getElementById('confirm').value;

      let hasError = false;
      ['nameField', 'emailField', 'passwordField', 'confirmField'].forEach((id) => setFieldError(id, false));

      if (!name) { setFieldError('nameField', true); hasError = true; }
      if (!isValidEmail(email)) { setFieldError('emailField', true); hasError = true; }
      if (!password || password.length < 6) { setFieldError('passwordField', true); hasError = true; }
      if (confirm !== password || !confirm) { setFieldError('confirmField', true); hasError = true; }
      if (hasError) return;

      const users = getUsers();
      if (users.some((u) => u.email === email)) {
        showBanner('An account with this email already exists on this browser. Try logging in instead.', 'error');
        return;
      }

      const newUser = { name, email, password };
      users.push(newUser);
      saveUsers(users);
      setSession(newUser, true);

      showBanner('Account created! Redirecting to your dashboard…', 'success');
      setTimeout(() => { window.location.href = 'dashboard.html'; }, 500);
    });
  }

  // ---------- Dashboard guard + shared session utilities ----------
  function guardDashboard() {
    const session = getSession();
    if (!session) {
      window.location.href = 'login.html';
    }
  }

  function getCurrentUser() {
    return getSession();
  }

  function logout() {
    clearSession();
    window.location.href = 'index.html';
  }

  ns.auth = {
    getUsers,
    saveUsers,
    setSession,
    getSession,
    clearSession,
    isValidEmail,
  };

  ns.initLoginPage = initLoginPage;
  ns.initSignupPage = initSignupPage;
  ns.guardDashboard = guardDashboard;
  ns.getCurrentUser = getCurrentUser;
  ns.logout = logout;
})(window.IPSAKTI);
