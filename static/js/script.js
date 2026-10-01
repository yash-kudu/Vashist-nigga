/* ==========================================================
   NutriHealth - script.js
   Plain vanilla JavaScript. No libraries. Handles:
     1. Mobile navigation toggle
     2. Client-side form validation (instant feedback only --
        the server in app.py re-validates everything for real)
     3. Small dynamic UI touches: calorie estimate while logging
        food, live BMI preview, and auto-dismissing flash messages
   ========================================================== */

document.addEventListener("DOMContentLoaded", function () {

  // ---------- 1. Mobile nav toggle ----------
  var navToggle = document.getElementById("navToggle");
  var mainNav = document.getElementById("mainNav");

  if (navToggle && mainNav) {
    navToggle.addEventListener("click", function () {
      var isOpen = mainNav.classList.toggle("open");
      navToggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
    });
  }

  // ---------- 2. Flash messages auto-dismiss ----------
  var flashes = document.querySelectorAll(".flash");
  flashes.forEach(function (flash) {
    setTimeout(function () {
      flash.style.opacity = "0";
      setTimeout(function () {
        flash.remove();
      }, 400);
    }, 4000);
  });

  // ---------- 3. Register form: live password match check ----------
  var registerForm = document.getElementById("registerForm");
  if (registerForm) {
    var password = document.getElementById("password");
    var confirmPassword = document.getElementById("confirm_password");
    var matchHint = document.getElementById("matchHint");

    function checkPasswordMatch() {
      if (!confirmPassword.value) {
        matchHint.textContent = "";
        matchHint.className = "hint";
        return;
      }
      if (password.value === confirmPassword.value) {
        matchHint.textContent = "Passwords match.";
        matchHint.className = "hint hint-good";
        confirmPassword.classList.remove("input-error");
      } else {
        matchHint.textContent = "Passwords do not match.";
        matchHint.className = "hint hint-bad";
        confirmPassword.classList.add("input-error");
      }
    }

    password.addEventListener("input", checkPasswordMatch);
    confirmPassword.addEventListener("input", checkPasswordMatch);

    registerForm.addEventListener("submit", function (e) {
      if (password.value.length < 6) {
        e.preventDefault();
        password.classList.add("input-error");
        matchHint.textContent = "Password must be at least 6 characters.";
        matchHint.className = "hint hint-bad";
      } else if (password.value !== confirmPassword.value) {
        e.preventDefault();
        checkPasswordMatch();
      }
    });
  }

  // ---------- 4. Log food form: live calorie estimate ----------
  var logFoodForm = document.getElementById("logFoodForm");
  if (logFoodForm) {
    var caloriesInput = document.getElementById("calories");
    var proteinInput = document.getElementById("protein");
    var carbsInput = document.getElementById("carbs");
    var fatsInput = document.getElementById("fats");
    var estimateHint = document.getElementById("calorieEstimateHint");

    function updateCalorieEstimate() {
      var protein = parseFloat(proteinInput.value) || 0;
      var carbs = parseFloat(carbsInput.value) || 0;
      var fats = parseFloat(fatsInput.value) || 0;

      if (protein === 0 && carbs === 0 && fats === 0) {
        estimateHint.textContent = "";
        return;
      }

      // Standard Atwater factors: 4 kcal/g protein, 4 kcal/g carbs, 9 kcal/g fat
      var estimate = Math.round(protein * 4 + carbs * 4 + fats * 9);
      estimateHint.textContent = "Estimated from macros: ~" + estimate + " kcal";

      // If the calories field is still empty, offer the estimate as a starting point
      if (!caloriesInput.value) {
        caloriesInput.placeholder = "~" + estimate + " kcal (from macros)";
      }
    }

    [proteinInput, carbsInput, fatsInput].forEach(function (input) {
      input.addEventListener("input", updateCalorieEstimate);
    });
  }

  // ---------- 5b. Dashboard: animate rings, bars, and numbers on load ----------
  // Every ring/bar is rendered by Jinja with its real --pct / width
  // already baked into the inline style. To animate "into" that
  // value, we read the target back out, reset to 0, force a reflow,
  // then set it back to the target so the CSS transition can play.
  var animatedRings = document.querySelectorAll(".calorie-ring, .score-ring");
  animatedRings.forEach(function (ring) {
    var target = ring.style.getPropertyValue("--pct") || "0";
    ring.style.setProperty("--pct", "0");
    void ring.offsetWidth; // force reflow so the 0 actually applies first
    requestAnimationFrame(function () {
      ring.style.setProperty("--pct", target);
    });
  });

  var animatedBars = document.querySelectorAll(".macro-bar-fill");
  animatedBars.forEach(function (bar) {
    var target = bar.style.width || "0%";
    bar.style.width = "0%";
    void bar.offsetWidth;
    requestAnimationFrame(function () {
      bar.style.width = target;
    });
  });

  // Count up any element flagged with data-countup from 0 to its
  // displayed integer value (used for calorie/step/score numbers).
  function countUp(el, duration) {
    var target = parseInt((el.textContent || "0").replace(/[^\d-]/g, ""), 10);
    if (isNaN(target)) return;
    var start = 0;
    var startTime = null;
    function step(timestamp) {
      if (!startTime) startTime = timestamp;
      var progress = Math.min(1, (timestamp - startTime) / duration);
      var value = Math.round(start + (target - start) * progress);
      el.textContent = value.toLocaleString();
      if (progress < 1) {
        requestAnimationFrame(step);
      } else {
        el.textContent = target.toLocaleString();
      }
    }
    requestAnimationFrame(step);
  }

  document.querySelectorAll(
    ".score-ring-inner strong, .calorie-ring-inner strong, .activity-card .tracker-count"
  ).forEach(function (el) {
    // Skip elements whose text contains a "/" (e.g. "3,200 / 10,000 steps") --
    // only count up the leading number, leave the rest of the label alone.
    if (el.children.length) return; // has nested <span>, handled separately below
    countUp(el, 900);
  });

  // Steps counter has a nested <span> for "/ goal steps", so count up
  // just the leading text node.
  document.querySelectorAll(".activity-card .tracker-count").forEach(function (el) {
    var firstNode = el.childNodes[0];
    if (!firstNode) return;
    var target = parseInt((firstNode.textContent || "0").replace(/[^\d]/g, ""), 10);
    if (isNaN(target)) return;
    var startTime = null;
    function step(timestamp) {
      if (!startTime) startTime = timestamp;
      var progress = Math.min(1, (timestamp - startTime) / 900);
      var value = Math.round(target * progress);
      firstNode.textContent = value.toLocaleString() + " ";
      if (progress < 1) requestAnimationFrame(step);
      else firstNode.textContent = target.toLocaleString() + " ";
    }
    requestAnimationFrame(step);
  });

  // ---------- 5c. Ragbot chat widget ----------
  var chatToggle = document.getElementById("chatbotToggle");
  var chatPanel = document.getElementById("chatbotPanel");
  var chatClose = document.getElementById("chatbotClose");
  var chatForm = document.getElementById("chatbotForm");
  var chatInput = document.getElementById("chatbotInput");
  var chatMessages = document.getElementById("chatbotMessages");

  if (chatToggle && chatPanel) {
    // Chat history + open/closed state are kept in sessionStorage, not
    // localStorage: sessionStorage survives a page reload (which is
    // what happens right after the bot logs food) but is automatically
    // cleared once the browser tab is closed, so nothing lingers
    // beyond "this session" the way the user asked.
    var CHAT_HISTORY_KEY = "nutrihealth_chat_history";
    var CHAT_OPEN_KEY = "nutrihealth_chat_open";

    function loadChatHistory() {
      try {
        var raw = sessionStorage.getItem(CHAT_HISTORY_KEY);
        return raw ? JSON.parse(raw) : [];
      } catch (e) {
        return []; // e.g. private browsing mode blocking storage
      }
    }

    function saveChatHistory(history) {
      try {
        sessionStorage.setItem(CHAT_HISTORY_KEY, JSON.stringify(history));
      } catch (e) { /* storage unavailable -- fail silently */ }
    }

    var chatHistory = loadChatHistory();

    function addChatMessage(text, who, persist) {
      var bubble = document.createElement("div");
      bubble.className = "chatbot-msg chatbot-msg-" + who;
      bubble.textContent = text;
      chatMessages.appendChild(bubble);
      chatMessages.scrollTop = chatMessages.scrollHeight;

      if (persist !== false) {
        chatHistory.push({ text: text, who: who });
        saveChatHistory(chatHistory);
      }
      return bubble;
    }

    // Restore any saved conversation from before the reload. If there
    // is none, the server-rendered welcome bubble already in the HTML
    // is left exactly as it is.
    if (chatHistory.length) {
      chatMessages.innerHTML = "";
      chatHistory.forEach(function (msg) {
        addChatMessage(msg.text, msg.who, false);
      });
    }

    // Restore whether the panel was open, so it reopens on its own
    // right after the reload-to-refresh-stats that follows a log.
    if (sessionStorage.getItem(CHAT_OPEN_KEY) === "1") {
      chatPanel.removeAttribute("hidden");
    }

    function setChatOpen(isOpen) {
      try {
        sessionStorage.setItem(CHAT_OPEN_KEY, isOpen ? "1" : "0");
      } catch (e) { /* ignore */ }
    }

    chatToggle.addEventListener("click", function () {
      var isHidden = chatPanel.hasAttribute("hidden");
      if (isHidden) {
        chatPanel.removeAttribute("hidden");
        chatInput.focus();
      } else {
        chatPanel.setAttribute("hidden", "");
      }
      setChatOpen(isHidden);
    });

    chatClose.addEventListener("click", function () {
      chatPanel.setAttribute("hidden", "");
      setChatOpen(false);
    });

    chatForm.addEventListener("submit", function (e) {
      e.preventDefault();
      var message = chatInput.value.trim();
      if (!message) return;

      addChatMessage(message, "user");
      chatInput.value = "";

      var typingBubble = document.createElement("div");
      typingBubble.className = "chatbot-msg chatbot-msg-typing";
      typingBubble.textContent = "...";
      chatMessages.appendChild(typingBubble);
      chatMessages.scrollTop = chatMessages.scrollHeight;

      fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: message })
      })
        .then(function (res) { return res.json(); })
        .then(function (data) {
          typingBubble.remove();
          addChatMessage(data.reply, "bot");
          // If food was actually logged, refresh the page shortly after
          // so the dashboard's numbers/rings/bars reflect it (and replay
          // their entrance animation). The chat history + open state
          // saved above survive that reload.
          if (data.logged) {
            setTimeout(function () { window.location.reload(); }, 1400);
          }
        })
        .catch(function () {
          typingBubble.remove();
          addChatMessage("Sorry, something went wrong reaching the assistant.", "bot");
        });
    });
  }

  // ---------- 5d. Log Food page: live search + auto-fill ----------
  var foodNameInput = document.getElementById("food_name");
  var foodSuggestionsBox = document.getElementById("foodSuggestions");
  var foodMatchHint = document.getElementById("foodMatchHint");

  if (foodNameInput && foodSuggestionsBox) {
    var searchTimer = null;

    function fillFoodFields(food) {
      document.getElementById("calories").value = food.calories;
      document.getElementById("protein").value = food.protein;
      document.getElementById("carbs").value = food.carbs;
      document.getElementById("fats").value = food.fats;
      var mealSelect = document.getElementById("meal_type");
      if (mealSelect && !mealSelect.value) {
        mealSelect.value = food.meal_type;
      }
      if (foodMatchHint) {
        foodMatchHint.textContent = "Auto-filled from NutriHealth's food database — feel free to adjust.";
      }
    }

    function renderSuggestions(items) {
      foodSuggestionsBox.innerHTML = "";
      if (!items.length) {
        foodSuggestionsBox.setAttribute("hidden", "");
        return;
      }
      items.forEach(function (food) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "food-suggestion-item";
        btn.innerHTML = "<span>" + food.name + "</span><span class=\"muted\">" + food.calories + " kcal</span>";
        btn.addEventListener("click", function () {
          foodNameInput.value = food.name;
          fillFoodFields(food);
          foodSuggestionsBox.setAttribute("hidden", "");
        });
        foodSuggestionsBox.appendChild(btn);
      });
      foodSuggestionsBox.removeAttribute("hidden");
    }

    foodNameInput.addEventListener("input", function () {
      var query = foodNameInput.value.trim();
      if (foodMatchHint) foodMatchHint.textContent = "";
      clearTimeout(searchTimer);
      if (query.length < 2) {
        foodSuggestionsBox.setAttribute("hidden", "");
        return;
      }
      searchTimer = setTimeout(function () {
        fetch("/api/foods/search?q=" + encodeURIComponent(query))
          .then(function (res) { return res.json(); })
          .then(renderSuggestions)
          .catch(function () { foodSuggestionsBox.setAttribute("hidden", ""); });
      }, 200);
    });

    document.addEventListener("click", function (e) {
      if (!foodSuggestionsBox.contains(e.target) && e.target !== foodNameInput) {
        foodSuggestionsBox.setAttribute("hidden", "");
      }
    });
  }

  // ---------- 5. Health metrics form: live BMI preview ----------
  var metricsForm = document.getElementById("metricsForm");
  if (metricsForm) {
    var weightInput = document.getElementById("weight");
    var heightInput = document.getElementById("height");
    var bmiPreview = document.getElementById("bmiPreview");

    function updateBmiPreview() {
      var weight = parseFloat(weightInput.value);
      var height = parseFloat(heightInput.value);

      if (!weight || !height) {
        bmiPreview.textContent = "";
        return;
      }

      var heightM = height / 100;
      var bmi = (weight / (heightM * heightM)).toFixed(1);
      var category = "Normal weight";
      if (bmi < 18.5) category = "Underweight";
      else if (bmi >= 25 && bmi < 30) category = "Overweight";
      else if (bmi >= 30) category = "Obese";

      bmiPreview.textContent = "Preview: BMI " + bmi + " (" + category + ")";
    }

    weightInput.addEventListener("input", updateBmiPreview);
    heightInput.addEventListener("input", updateBmiPreview);
  }

});
