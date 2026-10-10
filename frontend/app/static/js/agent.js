const executeButton = document.querySelector("#execute-button");
if (executeButton) {
  executeButton.addEventListener("click", async () => {
    const status = document.querySelector("#execute-status");
    status.textContent = "Executing...";
    try {
      const result = await apiRequest(`/api/v1/agent/runs/${executeButton.dataset.id}/execute`, { method: "POST" });
      const orders = result.purchase_orders || [];
      const firstOrder = orders[0]?.purchase_order_id || result.purchase_order_id;
      if (orders.length > 1) {
        window.location.href = "/purchase-orders";
      } else if (firstOrder) {
        window.location.href = `/purchase-orders/${firstOrder}`;
      } else {
        status.textContent = "No purchase orders were returned.";
      }
    } catch (error) {
      status.textContent = error.message;
    }
  });
}

