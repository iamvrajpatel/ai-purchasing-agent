function setRecoveryStatus(message) {
  const status = document.querySelector("#recovery-status");
  if (status) status.textContent = message;
}

const analyzeRecoveryButton = document.querySelector("#analyze-recovery-button");
if (analyzeRecoveryButton) {
  analyzeRecoveryButton.addEventListener("click", async () => {
    setRecoveryStatus("Analyzing recovery...");
    try {
      await apiRequest(`/api/v1/purchase-orders/${analyzeRecoveryButton.dataset.id}/recovery/analyze`, { method: "POST" });
      window.location.reload();
    } catch (error) {
      setRecoveryStatus(error.message);
    }
  });
}

const approveRecoveryButton = document.querySelector("#approve-recovery-button");
if (approveRecoveryButton) {
  approveRecoveryButton.addEventListener("click", async () => {
    setRecoveryStatus("Approving recovery...");
    try {
      await apiRequest(`/api/v1/recovery-cases/${approveRecoveryButton.dataset.id}/approve`, { method: "POST" });
      window.location.reload();
    } catch (error) {
      setRecoveryStatus(error.message);
    }
  });
}

const executeRecoveryButton = document.querySelector("#execute-recovery-button");
if (executeRecoveryButton) {
  executeRecoveryButton.addEventListener("click", async () => {
    setRecoveryStatus("Executing supplemental purchase order...");
    try {
      const result = await apiRequest(`/api/v1/recovery-cases/${executeRecoveryButton.dataset.id}/execute`, { method: "POST" });
      window.location.href = `/purchase-orders/${result.purchase_order_id}`;
    } catch (error) {
      setRecoveryStatus(error.message);
    }
  });
}
