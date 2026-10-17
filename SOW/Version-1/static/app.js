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

// Rich-text formatting for SOW narrative fields.
// The original textarea remains the submitted field, so no backend form changes are needed.
document.addEventListener("DOMContentLoaded", () => {
  if (typeof Quill === "undefined") return;
  const toolbarOptions = [
    ["bold", "italic", "underline", "strike"],
    [{ header: [2, 3, false] }],
    [{ list: "ordered" }, { list: "bullet" }],
    [{ indent: "-1" }, { indent: "+1" }],
    [{ color: [] }, { background: [] }],
    [{ align: [] }],
    ["blockquote", "link"],
    ["clean"]
  ];

  const editors = [];
  document.querySelectorAll("textarea.rich-text-source").forEach((textarea) => {
    const editorHost = document.createElement("div");
    editorHost.className = "rich-editor";
    textarea.insertAdjacentElement("afterend", editorHost);
    const initialValue = textarea.value || "";
    textarea.classList.add("rich-source-hidden");

    const quill = new Quill(editorHost, {
      theme: "snow",
      modules: { toolbar: toolbarOptions },
      placeholder: "Enter details… use the toolbar to format text."
    });

    // Existing database values may be plain text or previously saved HTML.
    if (/<\/?(p|br|strong|em|u|ol|ul|li|h[1-6]|blockquote|span|a)\b/i.test(initialValue)) {
      quill.clipboard.dangerouslyPasteHTML(initialValue);
    } else {
      quill.setText(initialValue);
    }
    editors.push({ textarea, quill });
  });

  const form = document.querySelector("#sow-form");
  if (form) {
    form.addEventListener("submit", () => {
      editors.forEach(({ textarea, quill }) => {
        textarea.value = quill.root.innerHTML;
      });
    });
    // Reset restores initial values and refreshes editors on the next browser tick.
    form.addEventListener("reset", () => {
      window.setTimeout(() => {
        editors.forEach(({ textarea, quill }) => {
          quill.setText(textarea.defaultValue || "");
        });
      }, 0);
    });
  }
});
