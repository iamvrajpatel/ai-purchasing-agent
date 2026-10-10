document.querySelectorAll(".approval-action").forEach((button) => {
  button.addEventListener("click", async () => {
    const action = button.dataset.action;
    button.disabled = true;
    try {
      const result = await apiRequest(`/api/v1/approvals/${button.dataset.id}/${action}`, { method: "POST" });
      if (action === "execute" && result.purchase_order_id) {
        window.location.href = `/purchase-orders/${result.purchase_order_id}`;
        return;
      }
      window.location.reload();
    } catch (error) {
      button.disabled = false;
      alert(error.message);
    }
  });
});

