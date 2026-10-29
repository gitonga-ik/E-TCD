const REQUEST_TIMEOUT_MS = 5 * 60 * 1000;
const MAX_FILE_SIZE = 50 * 1024 * 1024;

const form = document.getElementById("treeForm");
const imageInput = document.getElementById("imageInput");
const dropArea = document.getElementById("dropArea");
const fileName = document.getElementById("fileName");
const submitButton = document.getElementById("submitButton");
const statusBox = document.getElementById("status");
const placeholder = document.getElementById("placeholder");
const resultContent = document.getElementById("resultContent");
const treeCount = document.getElementById("treeCount");
const overlayImage = document.getElementById("overlayImage");
const downloadLink = document.getElementById("downloadLink");

const allowedExtensions = [".jpg", ".jpeg", ".png", ".tif", ".tiff"];

let activeObjectUrl = null;

function showStatus(message, type = "info") {
  statusBox.textContent = message;
  statusBox.className = `status visible ${type}`;
}

function clearStatus() {
  statusBox.textContent = "";
  statusBox.className = "status";
}

function getExtension(name) {
  const index = name.lastIndexOf(".");
  return index >= 0 ? name.slice(index).toLowerCase() : "";
}

function validateFile(file) {
  if (!file) {
    throw new Error("Please select an image first.");
  }

  if (!allowedExtensions.includes(getExtension(file.name))) {
    throw new Error("Please upload a JPG, PNG, or TIFF image.");
  }

  if (file.size > MAX_FILE_SIZE) {
    throw new Error("The image must not exceed 50 MB.");
  }

  if (file.size === 0) {
    throw new Error("The selected file is empty.");
  }
}

function setSelectedFile(file) {
  if (!file) return;

  try {
    validateFile(file);
    imageInput.files = createFileList(file);
    fileName.textContent = `${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`;
    clearStatus();
  } catch (error) {
    imageInput.value = "";
    fileName.textContent = "No image selected";
    showStatus(error.message, "error");
  }
}

// Create a FileList using the browser's DataTransfer API.
function createFileList(file) {
  const transfer = new DataTransfer();
  transfer.items.add(file);
  return transfer.files;
}

imageInput.addEventListener("change", () => {
  const file = imageInput.files[0];
  if (file) setSelectedFile(file);
});

dropArea.addEventListener("dragover", (event) => {
  event.preventDefault();
  dropArea.classList.add("dragover");
});

dropArea.addEventListener("dragleave", () => {
  dropArea.classList.remove("dragover");
});

dropArea.addEventListener("drop", (event) => {
  event.preventDefault();
  dropArea.classList.remove("dragover");

  const file = event.dataTransfer.files[0];
  if (file) setSelectedFile(file);
});

function validateCoordinates() {
  const lat = document.getElementById("latitude").value.trim();
  const lon = document.getElementById("longitude").value.trim();

  if ((lat && !lon) || (!lat && lon)) {
    throw new Error("Enter both latitude and longitude, or leave both empty.");
  }

  if (
    lat &&
    (!Number.isFinite(Number(lat)) || Number(lat) < -90 || Number(lat) > 90)
  ) {
    throw new Error("Latitude must be between -90 and 90.");
  }

  if (
    lon &&
    (!Number.isFinite(Number(lon)) || Number(lon) < -180 || Number(lon) > 180)
  ) {
    throw new Error("Longitude must be between -180 and 180.");
  }

  // Coordinates are intentionally not sent to the API yet.
}

function decodeBase64Image(base64) {
  // Support either raw base64 or a data URL.
  const cleanBase64 = base64.replace(
    /^data:image\/[a-zA-Z0-9.+-]+;base64,/,
    "",
  );

  const binary = atob(cleanBase64);
  const bytes = new Uint8Array(binary.length);

  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }

  return new Blob([bytes], { type: "image/png" });
}

function displayResult(data) {
  if (!Number.isInteger(data.tree_count) || data.tree_count < 0) {
    throw new Error("The API returned an invalid tree count.");
  }

  if (typeof data.image !== "string" || !data.image.length) {
    throw new Error("The API did not return an overlay image.");
  }

  const imageBlob = decodeBase64Image(data.image);
  const newObjectUrl = URL.createObjectURL(imageBlob);

  if (activeObjectUrl) {
    URL.revokeObjectURL(activeObjectUrl);
  }

  activeObjectUrl = newObjectUrl;

  treeCount.textContent = data.tree_count.toLocaleString();
  overlayImage.src = newObjectUrl;
  downloadLink.href = newObjectUrl;

  placeholder.style.display = "none";
  resultContent.classList.add("visible");
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearStatus();

  let file;

  try {
    file = imageInput.files[0];
    validateFile(file);
    validateCoordinates();

    const gsd = Number(document.getElementById("gsd").value);

    if (!Number.isFinite(gsd) || gsd <= 0 || gsd > 100) {
      throw new Error(
        "Ground sampling distance must be greater than 0 and at most 100.",
      );
    }
  } catch (error) {
    showStatus(error.message, "error");
    return;
  }

  const gsd = Number(document.getElementById("gsd").value);
  const formData = new FormData();

  formData.append("file", file);

  submitButton.disabled = true;
  submitButton.innerHTML = '<span class="spinner"></span>Processing image...';

  showStatus(
    "Your image is being analyzed. Large images may take several minutes. Please keep this page open.",
    "info",
  );

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(
      `/count-trees?gsd=${encodeURIComponent(gsd)}`,
      {
        method: "POST",
        body: formData,
        signal: controller.signal,
      },
    );

    const responseText = await response.text();
    let data;

    try {
      data = JSON.parse(responseText);
    } catch {
      throw new Error(
        `The server returned an invalid response (HTTP ${response.status}).`,
      );
    }

    if (!response.ok) {
      const detail =
        typeof data.detail === "string"
          ? data.detail
          : `Request failed with HTTP ${response.status}.`;

      throw new Error(detail);
    }

    displayResult(data);
    showStatus("Tree counting completed successfully.", "success");
  } catch (error) {
    if (error.name === "AbortError") {
      showStatus(
        "The request exceeded the five-minute client timeout. " +
          "The server may still be processing your image. " +
          "Check the server logs before retrying.",
        "error",
      );
    } else if (error instanceof TypeError) {
      showStatus(
        "Could not connect to the API. Check that FastAPI is running, " +
          "the API URL is correct, and CORS is configured if needed.",
        "error",
      );
    } else {
      showStatus(error.message || "An unexpected error occurred.", "error");
    }
  } finally {
    clearTimeout(timeoutId);
    submitButton.disabled = false;
    submitButton.textContent = "Count Trees";
  }
});

window.addEventListener("beforeunload", () => {
  if (activeObjectUrl) {
    URL.revokeObjectURL(activeObjectUrl);
  }
});
