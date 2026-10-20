document.addEventListener("DOMContentLoaded", () => {
  const resourceBody = document.querySelector("#resources-table tbody");
  const milestoneBody = document.querySelector("#milestones-table tbody");
  document.querySelector("#add-resource").addEventListener("click", () => {
    resourceBody.appendChild(document.querySelector("#resource-row-template").content.cloneNode(true));
  });
  document.querySelector("#add-milestone").addEventListener("click", () => {
    milestoneBody.appendChild(document.querySelector("#milestone-row-template").content.cloneNode(true));
  });
  document.addEventListener("click", (event) => {
    const button = event.target.closest(".remove-row");
    if (button) button.closest("tr").remove();
  });

  // Section navigator: open the target section, scroll it into view, and mark active link.
  const navLinks = [...document.querySelectorAll(".nav-link")];
  navLinks.forEach((link) => {
    link.addEventListener("click", () => {
      const target = document.querySelector(link.getAttribute("href"));
      if (target && target.tagName.toLowerCase() === "details") target.open = true;
      navLinks.forEach((item) => item.classList.toggle("active", item === link));
    });
  });

  // Keep the navigator highlight in sync with the section nearest the viewport.
  const sections = [...document.querySelectorAll("details.collapsible")];
  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver((entries) => {
      const visible = entries.filter((entry) => entry.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (visible) navLinks.forEach((link) =>
        link.classList.toggle("active", link.getAttribute("href") === "#" + visible.target.id));
    }, { rootMargin: "-15% 0px -65% 0px", threshold: [0, 0.1, 0.25] });
    sections.forEach((section) => observer.observe(section));
  }
});

// Lightweight native rich-text editor for SOW narrative fields.
// Uses browser editing commands; no third-party CDN or external JavaScript is required.
document.addEventListener("DOMContentLoaded", () => {
  const editors = [];

  const toolbarButtons = [
    { label: "B", command: "bold", title: "Bold", className: "editor-bold" },
    { label: "I", command: "italic", title: "Italic", className: "editor-italic" },
    { label: "U", command: "underline", title: "Underline", className: "editor-underline" },
    { label: "• List", command: "insertUnorderedList", title: "Bulleted list" },
    { label: "1. List", command: "insertOrderedList", title: "Numbered list" },
    { label: "H2", command: "formatBlock", value: "h2", title: "Heading" },
    { label: "Quote", command: "formatBlock", value: "blockquote", title: "Block quote" },
    { label: "Clear", command: "removeFormat", title: "Clear formatting" }
  ];

  document.querySelectorAll("textarea.rich-text-source").forEach((textarea) => {
    const host = document.createElement("div");
    host.className = "rich-editor";

    const toolbar = document.createElement("div");
    toolbar.className = "native-editor-toolbar";
    toolbar.setAttribute("role", "toolbar");
    toolbar.setAttribute("aria-label", "Text formatting");

    const editor = document.createElement("div");
    editor.className = "native-rich-editable";
    editor.contentEditable = "true";
    editor.setAttribute("role", "textbox");
    editor.setAttribute("aria-multiline", "true");
    editor.setAttribute("aria-label", textarea.closest("label")?.childNodes?.[0]?.textContent?.trim() || "Rich text editor");
    editor.dataset.placeholder = "Enter details… use the toolbar to format text.";

    const initialValue = (textarea.value || "").trim();
    if (/<\/?(p|br|strong|b|em|i|u|ol|ul|li|h[1-6]|blockquote|span|a)\b/i.test(initialValue)) {
      editor.innerHTML = initialValue;
    } else {
      editor.textContent = textarea.value || "";
      editor.innerHTML = editor.innerHTML.replace(/\n/g, "<br>");
    }

    toolbarButtons.forEach((item) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "native-editor-button " + (item.className || "");
      button.textContent = item.label;
      button.title = item.title;
      button.setAttribute("aria-label", item.title);
      // Keep the current selection inside the editable region when clicking toolbar controls.
      button.addEventListener("mousedown", (event) => event.preventDefault());
      button.addEventListener("click", () => {
        editor.focus();
        if (item.value) document.execCommand(item.command, false, item.value);
        else document.execCommand(item.command, false, null);
        syncValue();
      });
      toolbar.appendChild(button);
    });

    host.appendChild(toolbar);
    host.appendChild(editor);
    textarea.insertAdjacentElement("afterend", host);
    textarea.classList.add("rich-source-hidden");

    function syncValue() {
      textarea.value = editor.innerHTML;
    }
    editor.addEventListener("input", syncValue);
    editor.addEventListener("blur", syncValue);
    editors.push({ textarea, editor, syncValue });
  });

  const form = document.querySelector("#sow-form");
  if (form) {
    form.addEventListener("submit", () => {
      editors.forEach(({ syncValue }) => syncValue());
    });
    form.addEventListener("reset", () => {
      window.setTimeout(() => {
        editors.forEach(({ textarea, editor, syncValue }) => {
          const value = textarea.defaultValue || "";
          if (/<\/?(p|br|strong|b|em|i|u|ol|ul|li|h[1-6]|blockquote|span|a)\b/i.test(value)) {
            editor.innerHTML = value;
          } else {
            editor.textContent = value;
            editor.innerHTML = editor.innerHTML.replace(/\n/g, "<br>");
          }
          syncValue();
        });
      }, 0);
    });
  }
});


// Final-save confirmation modal. Server-side validation is authoritative.
document.addEventListener("DOMContentLoaded", () => {
  const openButton = document.getElementById("open-save-confirm");
  const modal = document.getElementById("save-confirm-modal");
  if (!modal) return;

  const form = modal.querySelector("#final-save-form");
  const cancelButton = document.getElementById("cancel-save-confirm");
  const version = modal.querySelector('input[name="sow_version"]');
  const summary = modal.querySelector('textarea[name="change_summary"]');

  const openModal = () => {
    modal.hidden = false;
    document.body.classList.add("modal-open");
    (version || summary)?.focus();
  };
  const closeModal = () => {
    modal.hidden = true;
    document.body.classList.remove("modal-open");
    openButton?.focus();
  };

  if (openButton) openButton.addEventListener("click", openModal);
  cancelButton?.addEventListener("click", closeModal);
  modal.addEventListener("click", (event) => {
    if (event.target === modal) closeModal();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.hidden) closeModal();
  });

  form?.addEventListener("submit", (event) => {
    const missing = !version?.value.trim() || !summary?.value.trim();
    if (missing) {
      event.preventDefault();
      if (summary && !summary.value.trim()) {
        summary.setCustomValidity("Please enter a change summary before saving.");
        summary.reportValidity();
        summary.focus();
      } else if (version) {
        version.setCustomValidity("Please enter an SOW version before saving.");
        version.reportValidity();
        version.focus();
      }
      return;
    }
    summary?.setCustomValidity("");
    version?.setCustomValidity("");
    const submitButton = form.querySelector('button[type="submit"]');
    if (submitButton) {
      submitButton.disabled = true;
      submitButton.textContent = "Generating PDF and saving…";
    }
  });
  summary?.addEventListener("input", () => summary.setCustomValidity(""));
  version?.addEventListener("input", () => version.setCustomValidity(""));

  // When the server rejects an incomplete confirmation, keep the modal visible.
  if (!modal.hidden) document.body.classList.add("modal-open");
});
