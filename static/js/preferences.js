const languageSelect = document.querySelector("#musicLanguage");
const kpopGroupField = document.querySelector("#kpopGroupField");
const kpopGroupSelect = document.querySelector("#kpopGroup");

function updateKpopGroupField() {
  const showKpopGroups = languageSelect.value === "韓文／K-pop";
  kpopGroupField.hidden = !showKpopGroups;
  kpopGroupSelect.disabled = !showKpopGroups;
  if (!showKpopGroups) kpopGroupSelect.value = "";
}

languageSelect.addEventListener("change", updateKpopGroupField);
updateKpopGroupField();
