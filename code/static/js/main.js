// main.js — global JS for EPARS
// Most page logic lives in the template <script> blocks.
// This file is for any shared utilities.

// Highlight active nav item based on current path
document.addEventListener("DOMContentLoaded", () => {
  const path = window.location.pathname;
  document.querySelectorAll(".nav-item").forEach(item => {
    if (item.getAttribute("href") && path.startsWith(item.getAttribute("href")) && item.getAttribute("href") !== "/") {
      item.classList.add("active");
    }
  });
});
