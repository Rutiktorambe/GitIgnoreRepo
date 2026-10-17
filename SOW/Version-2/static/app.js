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
});