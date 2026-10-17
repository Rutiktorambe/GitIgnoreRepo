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