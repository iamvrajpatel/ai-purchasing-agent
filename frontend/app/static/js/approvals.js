document.querySelectorAll(".approval-action").forEach((button) => {
  button.addEventListener("click", async () => {
    const action = button.dataset.action;
    button.disabled = true;
    try {
      await apiRequest(`/api/v1/approvals/${button.dataset.id}/${action}`, { method: "POST" });
      window.location.reload();
    } catch (error) {
      button.disabled = false;
      alert(error.message);
    }
  });
});

