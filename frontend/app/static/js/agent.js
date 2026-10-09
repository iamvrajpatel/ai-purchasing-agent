const executeButton = document.querySelector("#execute-button");
if (executeButton) {
  executeButton.addEventListener("click", async () => {
    const status = document.querySelector("#execute-status");
    status.textContent = "Executing...";
    try {
      const result = await apiRequest(`/api/v1/agent/runs/${executeButton.dataset.id}/execute`, { method: "POST" });
      window.location.href = `/purchase-orders/${result.purchase_order_id}`;
    } catch (error) {
      status.textContent = error.message;
    }
  });
}

