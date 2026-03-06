/**
 * main.js – client-side interactions for the Flower Recognizer upload form.
 */

(function () {
  "use strict";

  const dropZone = document.getElementById("dropZone");
  const fileInput = document.getElementById("imageInput");
  const previewGrid = document.getElementById("previewGrid");
  const submitBtn = document.getElementById("submitBtn");
  const uploadForm = document.getElementById("uploadForm");
  const overlay = document.getElementById("loadingOverlay");

  if (!dropZone) return; // not on index page

  // ── File validation ──────────────────────────────────────────────────────
  const ALLOWED_TYPES = ["image/jpeg", "image/png"];
  const MAX_SIZE_MB = 16;

  function isValid(file) {
    if (!ALLOWED_TYPES.includes(file.type)) {
      alert(
        `"${file.name}" is not a supported format. Please upload JPG or PNG files.`,
      );
      return false;
    }
    if (file.size > MAX_SIZE_MB * 1024 * 1024) {
      alert(`"${file.name}" exceeds the ${MAX_SIZE_MB} MB limit.`);
      return false;
    }
    return true;
  }

  // ── Preview rendering ────────────────────────────────────────────────────
  let selectedFiles = [];

  function renderPreviews(files) {
    previewGrid.innerHTML = "";
    files.forEach((file) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        const img = document.createElement("img");
        img.src = e.target.result;
        img.alt = file.name;
        img.title = file.name;
        img.className = "preview-grid__item";
        previewGrid.appendChild(img);
      };
      reader.readAsDataURL(file);
    });
    submitBtn.disabled = files.length === 0;
  }

  function handleFiles(files) {
    const valid = Array.from(files).filter(isValid);
    if (valid.length === 0) return;
    selectedFiles = valid;

    // Sync back to the native input via DataTransfer
    const dt = new DataTransfer();
    valid.forEach((f) => dt.items.add(f));
    fileInput.files = dt.files;

    renderPreviews(valid);
  }

  // ── Drag & drop ──────────────────────────────────────────────────────────
  dropZone.addEventListener("click", (e) => {
    if (!e.target.closest("label")) fileInput.click();
  });

  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("drag-over");
  });

  ["dragleave", "dragend"].forEach((evt) => {
    dropZone.addEventListener(evt, () =>
      dropZone.classList.remove("drag-over"),
    );
  });

  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("drag-over");
    handleFiles(e.dataTransfer.files);
  });

  // ── File input change ────────────────────────────────────────────────────
  fileInput.addEventListener("change", () => handleFiles(fileInput.files));

  // ── Form submit — show loading overlay ───────────────────────────────────
  uploadForm.addEventListener("submit", (e) => {
    if (selectedFiles.length === 0) {
      e.preventDefault();
      alert("Please select at least one image before submitting.");
      return;
    }
    if (overlay) overlay.classList.remove("hidden");
    submitBtn.disabled = true;
    submitBtn.textContent = "Processing…";
  });
})();
