const analyzeButton = document.querySelector("#analyze-button");
if (analyzeButton) {
  analyzeButton.addEventListener("click", async () => {
    const status = document.querySelector("#action-status");
    const errorBox = document.querySelector("#analysis-error");
    status.textContent = "Starting investigation...";
    errorBox.classList.add("hidden");
    try {
      const run = await apiRequest("/api/v1/agent/analyze", {
        method: "POST",
        body: JSON.stringify({ recommendation_id: Number(analyzeButton.dataset.id) }),
      });
      window.location.href = `/agent/runs/${run.id}`;
    } catch (error) {
      status.textContent = "";
      errorBox.textContent = error.message;
      errorBox.classList.remove("hidden");
    }
  });
}

