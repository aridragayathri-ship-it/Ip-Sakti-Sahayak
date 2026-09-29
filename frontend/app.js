/* ============================================================
   IP-SAKTI — app.js
   Dashboard interactivity. Ask IP-SAKTI and Product Classification
   call the FastAPI backend at API_BASE. If the backend can't be
   reached (not running, wrong port, CORS misconfigured, etc.), the
   UI falls back to small built-in sample logic so the prototype
   still demonstrates the intended experience on its own.
   ============================================================ */

window.IPSAKTI = window.IPSAKTI || {};

(function (ns) {

  // Change this if your backend runs somewhere else.
 const API_BASE = "https://ip-sakti-sahayak-dppy.onrender.com";

  let currentJurisdiction = 'india';


  // ---------- view switching ----------

  function switchView(viewName) {
    document.querySelectorAll('.view').forEach((v) =>
      v.classList.remove('active')
    );

    document.querySelectorAll('#appNav button').forEach((b) =>
      b.classList.remove('active')
    );

    const target = document.getElementById('view-' + viewName);

    if (target) {
      target.classList.add('active');
    }

    document
      .querySelectorAll('#appNav button[data-view="' + viewName + '"]')
      .forEach((b) => b.classList.add('active'));

    window.scrollTo({
      top: 0,
      behavior: 'smooth'
    });
  }


  function wireNav() {
    document.querySelectorAll('[data-view]').forEach((el) => {
      el.addEventListener('click', () =>
        switchView(el.getAttribute('data-view'))
      );
    });
  }


  // ---------- header / user ----------

  function renderUser() {
    const user = ns.getCurrentUser();

    if (!user) return;

    const initial = (user.name || user.email || '?')
      .trim()
      .charAt(0)
      .toUpperCase();

    document.getElementById('userAvatar').textContent = initial || '?';
    document.getElementById('userName').textContent =
      user.name || user.email;
  }


  function wireLogout() {
    document
      .getElementById('logoutBtn')
      .addEventListener('click', () => ns.logout());
  }


  // ---------- lightweight local category hint ----------

  const categoryHints = [
    {
      test: (q) => /cosmetic|cream|skin|lotion|serum/i.test(q),
      label: 'Cosmetic'
    },

    {
      test: (q) => /tea|food|drink|supplement|beverage/i.test(q),
      label: 'Herbal Food / Supplement'
    },

    {
      test: (q) => /export|international|abroad|overseas|global/i.test(q),
      label: 'Cross-border Compliance'
    },

    {
      test: (q) =>
        /traditional|classical|ancient|tkdl|grandmother|generations/i.test(q),
      label: 'Traditional Knowledge-linked'
    }
  ];


  function categoryHintFor(question) {
    const hit = categoryHints.find((h) => h.test(question));

    return hit
      ? hit.label
      : 'General Ayurvedic Formulation';
  }


  const fallbackSteps = [
    'Run a prior-art and traditional-knowledge search before drafting any claims.',
    'Clarify the exact product category: drug, food, supplement or cosmetic.',
    'Speak with a qualified IP or regulatory professional before filing anything.'
  ];


  // ---------- Ask IP-SAKTI ----------

  async function callAskApi(question, jurisdiction) {

    const response = await fetch(`${API_BASE}/api/ask`, {
      method: 'POST',

      headers: {
        'Content-Type': 'application/json'
      },

      // FIX:
      // Backend requires question + jurisdiction + user_id
      body: JSON.stringify({
        question: question,
        jurisdiction: jurisdiction,
        user_id: 1
      })
    });


    if (!response.ok) {
      throw new Error(
        'Backend responded with status ' + response.status
      );
    }


    return response.json();
  }


  function localFallbackAnswer(question, jurisdictionLabel) {

    return {
      answer:
        `Backend offline — showing a built-in sample response. In a running setup, this would be grounded in your PDF knowledge base for the ${jurisdictionLabel} jurisdiction.`,

      confidence: 'Low',

      mode: 'Demo Mode (offline)',

      evidence: []
    };
  }


  function confidenceBadgeClass(confidence) {

    const normalized = (confidence || '').toLowerCase();

    if (normalized === 'high') {
      return 'confidence-high';
    }

    if (normalized === 'medium') {
      return 'confidence-medium';
    }

    return 'confidence-low';
  }


  function escapeHtml(value) {

    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }


  function renderEvidence(evidence) {

    const block =
      document.getElementById('resultEvidenceBlock');

    const list =
      document.getElementById('resultEvidenceList');

    list.innerHTML = '';


    if (!evidence || evidence.length === 0) {

      block.style.display = 'none';

      return;
    }


    evidence.forEach((item) => {

      const card = document.createElement('div');

      card.className = 'evidence-mini-card';


      card.innerHTML = `
        <div class="evidence-mini-top">
          <strong>
            ${escapeHtml(item.document || 'Unknown document')}
            &middot;
            Page ${escapeHtml(item.page ?? '—')}
          </strong>

          <span>
            ${escapeHtml(item.source || 'Prototype Knowledge Base')}
          </span>
        </div>

        <p class="evidence-mini-excerpt">
          ${escapeHtml(item.excerpt || '')}
        </p>
      `;


      list.appendChild(card);
    });


    block.style.display = 'block';
  }


  async function renderAskResult(question) {

    const jurisdictionLabel =
      currentJurisdiction === 'india'
        ? 'India'
        : 'International';


    const analyzeBtn =
      document.getElementById('analyzeBtn');

    const originalBtnText =
      analyzeBtn.textContent;


    analyzeBtn.disabled = true;

    analyzeBtn.textContent = 'Analyzing…';


    let data;


    try {

      data = await callAskApi(
        question,
        jurisdictionLabel
      );

    } catch (err) {

      console.warn(
        'IP-SAKTI backend unreachable, using local fallback:',
        err
      );

      data =
        localFallbackAnswer(
          question,
          jurisdictionLabel
        );

    } finally {

      analyzeBtn.disabled = false;

      analyzeBtn.textContent = originalBtnText;
    }


    document.getElementById('resultAnswer').textContent =
      data.answer;


    document.getElementById('resultCategory').textContent =
      categoryHintFor(question);


    document.getElementById('resultJurisdiction').textContent =
      jurisdictionLabel;


    document.getElementById('resultConfidenceValue').textContent =
      data.confidence;


    const badge =
      document.getElementById('confidenceBadge');


    badge.textContent =
      'Confidence: ' + data.confidence;


    badge.className =
      'confidence-badge ' +
      confidenceBadgeClass(data.confidence);


    const modeBadge =
      document.getElementById('modeBadge');


    modeBadge.textContent =
      data.mode || 'Demo Mode';


    const stepsList =
      document.getElementById('resultSteps');


    stepsList.innerHTML = '';


    fallbackSteps.forEach((step) => {

      const li =
        document.createElement('li');

      li.textContent = step;

      stepsList.appendChild(li);
    });


    renderEvidence(data.evidence);


    document
      .getElementById('askResult')
      .classList.add('show');


    document
      .getElementById('askResult')
      .scrollIntoView({
        behavior: 'smooth',
        block: 'nearest'
      });
  }


  function wireAskView() {

    const jurisdictionSelect =
      document.getElementById('jurisdictionSelect');


    jurisdictionSelect.addEventListener('click', (e) => {

      const btn =
        e.target.closest('button[data-value]');

      if (!btn) return;


      currentJurisdiction =
        btn.getAttribute('data-value');


      jurisdictionSelect
        .querySelectorAll('button')
        .forEach((b) =>
          b.classList.remove('active')
        );


      btn.classList.add('active');
    });


    document
      .getElementById('analyzeBtn')
      .addEventListener('click', () => {

        const question =
          document
            .getElementById('askInput')
            .value
            .trim();


        if (!question) {

          document
            .getElementById('askInput')
            .focus();

          return;
        }


        renderAskResult(question);
      });


    document
      .getElementById('exampleChips')
      .addEventListener('click', (e) => {

        const chip =
          e.target.closest('.example-chip');

        if (!chip) return;


        const q =
          chip.getAttribute('data-q');


        document
          .getElementById('askInput')
          .value = q;


        renderAskResult(q);
      });
  }


  // ---------- Product Classification ----------

  async function callClassifyApi(payload) {

    const response =
      await fetch(`${API_BASE}/api/classify`, {

        method: 'POST',

        headers: {
          'Content-Type': 'application/json'
        },

        body: JSON.stringify(payload)
      });


    if (!response.ok) {

      throw new Error(
        'Backend responded with status ' +
        response.status
      );
    }


    return response.json();
  }


  function localFallbackClassify(payload) {

    const {
      productType,
      tk,
      market
    } = payload;


    let category =
      'Unclassified / Needs Manual Review';

    let ip =
      ['Manual review recommended'];

    let reg =
      ['Manual review recommended'];


    if (
      tk === 'Yes' ||
      productType === 'Classical formulation'
    ) {

      category =
        'Classical Ayurvedic Formulation';

      ip = [
        'Patent',
        'Traditional Knowledge',
        'Trademark'
      ];

      reg = [
        'Applicable Ayurvedic regulatory requirements'
      ];

    } else if (
      productType === 'Cosmetic'
    ) {

      category =
        'Ayurvedic Cosmetic';

      ip = [
        'Trademark',
        'Design'
      ];

      reg = [
        'Cosmetic regulatory requirements'
      ];

    } else if (
      productType ===
      'Ayurveda-Aahar/nutraceutical'
    ) {

      category =
        'Ayurveda-Aahar / Nutraceutical';

      ip = [
        'Trademark',
        'Trade Secret'
      ];

      reg = [
        'Food / nutraceutical regulatory requirements'
      ];

    } else if (
      productType === 'Phytopharmaceutical'
    ) {

      category =
        'Phytopharmaceutical';

      ip = [
        'Patent',
        'Trade Secret'
      ];

      reg = [
        'Phytopharmaceutical drug regulatory pathway'
      ];

    } else if (
      productType === 'Proprietary medicine'
    ) {

      category =
        'Proprietary Ayurvedic Medicine';

      ip = [
        'Patent',
        'Trademark',
        'Trade Secret'
      ];

      reg = [
        'Applicable Ayurvedic regulatory requirements'
      ];

    } else if (
      productType === 'New/non-classical drug'
    ) {

      category =
        'New / Non-Classical Ayurvedic Drug';

      ip = [
        'Patent',
        'Trade Secret',
        'Trademark'
      ];

      reg = [
        'Applicable Ayurvedic regulatory requirements',
        'Safety and efficacy documentation'
      ];
    }


    if (
      market === 'International' ||
      market === 'Both'
    ) {

      reg = reg.concat([
        'Destination-market regulatory classification may differ from India'
      ]);
    }


    return {
      category,
      ip_considerations: ip,
      regulatory_considerations: reg,
      confidence: 'Low',
      offline: true
    };
  }


  function renderClassifyResult(result) {

    const container =
      document.getElementById('classifyResult');


    const ipList =
      (result.ip_considerations || [])
        .map((i) =>
          `<li>${escapeHtml(i)}</li>`
        )
        .join('');


    const regList =
      (result.regulatory_considerations || [])
        .map((i) =>
          `<li>${escapeHtml(i)}</li>`
        )
        .join('');


    const offlineNote =
      result.offline
        ? '<p class="result-disclaimer" style="margin-top:12px;">Backend offline — showing a local sample result.</p>'
        : '';


    container.innerHTML = `

      <div>

        <span class="evidence-tag">
          Sample classification · Confidence:
          ${escapeHtml(result.confidence || '—')}
        </span>


        <h3 style="margin-top:10px;">
          ${escapeHtml(result.category)}
        </h3>


        <div style="margin-top:14px;">

          <strong
            style="font-size:0.85rem; color:var(--teal-900);"
          >
            IP considerations
          </strong>


          <ul
            style="margin:6px 0 0; padding-left:20px; color:var(--ink-700); font-size:0.92rem;"
          >
            ${ipList}
          </ul>

        </div>


        <div style="margin-top:14px;">

          <strong
            style="font-size:0.85rem; color:var(--teal-900);"
          >
            Regulatory considerations
          </strong>


          <ul
            style="margin:6px 0 0; padding-left:20px; color:var(--ink-700); font-size:0.92rem;"
          >
            ${regList}
          </ul>

        </div>


        ${offlineNote}


        <p
          class="result-disclaimer"
          style="margin-top:16px;"
        >
          Generated from prototype sample logic —
          not a regulatory determination.
        </p>

      </div>
    `;
  }


  function wireClassifyView() {

    document
      .getElementById('classifyForm')
      .addEventListener('submit', async (e) => {

        e.preventDefault();


        const form = e.target;


        const productType =
          form
            .querySelector(
              'input[name="productType"]:checked'
            )
            .value;


        const tk =
          form
            .querySelector(
              'input[name="tk"]:checked'
            )
            .value;


        const bio =
          form
            .querySelector(
              'input[name="bio"]:checked'
            )
            .value;


        const market =
          form
            .querySelector(
              'input[name="market"]:checked'
            )
            .value;


        const submitBtn =
          form.querySelector(
            'button[type="submit"]'
          );


        const originalText =
          submitBtn.textContent;


        submitBtn.disabled = true;

        submitBtn.textContent =
          'Classifying…';


        let result;


        try {

          result =
            await callClassifyApi({

              product_type: productType,

              traditional_knowledge: tk,

              biological_resources: bio,

              target_market: market

            });

        } catch (err) {

          console.warn(
            'IP-SAKTI backend unreachable, using local fallback:',
            err
          );


          result =
            localFallbackClassify({
              productType,
              tk,
              bio,
              market
            });

        } finally {

          submitBtn.disabled = false;

          submitBtn.textContent =
            originalText;
        }


        renderClassifyResult(result);
      });
  }


  // ---------- init ----------

  function initDashboard() {

    renderUser();

    wireNav();

    wireLogout();

    wireAskView();

    wireClassifyView();
  }


  ns.initDashboard =
    initDashboard;

})(window.IPSAKTI);