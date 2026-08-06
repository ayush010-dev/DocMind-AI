const API_URL = "http://127.0.0.1:8001";

let documentId = null;

const fileInput = document.getElementById("fileInput");
const uploadBtn = document.getElementById("uploadBtn");
const uploadStatus = document.getElementById("uploadStatus");

const questionBox = document.getElementById("question");
const sendBtn = document.getElementById("sendBtn");

const chatBox = document.getElementById("chatBox");
const fileCard = document.getElementById("fileCard");
const fileName = document.getElementById("fileName");
const fileChunks = document.getElementById("fileChunks");

questionBox.addEventListener("keypress", function (e) {

    if (e.key === "Enter" && !e.shiftKey) {

        e.preventDefault();

        sendBtn.click();

    }

});


// Upload Document

uploadBtn.addEventListener("click", async (e) => {
    e.preventDefault();
    console.log("Upload button clicked");
    const file = fileInput.files[0];
    console.log(file);

    if (!file) {

        alert("Please choose a file.");

        return;
    }

    const formData = new FormData();

    formData.append("file", file);

    uploadStatus.innerText = "Uploading...";

    try {

        const response = await fetch(`${API_URL}/upload`, {

            method: "POST",

            body: formData

        });

        const data = await response.json();
        console.log(data);

        documentId = data.document_id;

        uploadStatus.innerText = "";

            fileCard.classList.remove("hidden");

            fileName.innerText = data.filename;

            fileChunks.innerText =
            `${data.chunks} chunks indexed successfully`;

            documentId = data.document_id;

    }

    catch (error) {

        uploadStatus.innerText =
            "❌ Upload Failed.";

        console.error(error);

    }

});


// Ask Question

sendBtn.addEventListener("click", async () => {

    if (!documentId) {

        alert("Upload a document first.");

        return;

    }

    const question = questionBox.value.trim();

    if (!question) {

        return;

    }

    addMessage("You", question, "user");

    questionBox.value = "";

    sendBtn.disabled = true;

    sendBtn.innerText = "Thinking...";

    try {

        const response = await fetch(`${API_URL}/chat`, {

            method: "POST",

            headers: {

                "Content-Type": "application/json"

            },

            body: JSON.stringify({

                question: question,

                document_id: documentId

            })

        });

        const data = await response.json();

        addMessage(

            "DocMind AI",

            `${data.answer}

            Source: ${data.source}

            Chunk: ${data.chunk}`,

            "ai"

);

        sendBtn.disabled = false;

        sendBtn.innerText = "Send";

    }

    catch (error) {

    console.log(error);

    addMessage(

        "DocMind AI",

        "Something went wrong.",

        "ai"

    );

    sendBtn.disabled = false;

    sendBtn.innerText = "Send";

}

});


// Show Messages

function addMessage(sender, message, type) {

    const div = document.createElement("div");

    div.className = `message ${type}`;

    div.innerHTML = `

        <strong>${sender}</strong>

        <p>${message}</p>

    `;

    chatBox.appendChild(div);

    chatBox.scrollTop = chatBox.scrollHeight;

}

