const express = require("express");
const cors = require("cors");
const dotenv = require("dotenv");

const http = require("http");
const { Server } = require("socket.io");

dotenv.config();

const connectDB = require("./config/db");

const attendanceRoutes = require("./routes/attendanceRoutes");

const app = express();

connectDB();

app.use(cors());
app.use(express.json());

const path = require("path");
app.use(express.static(
    path.join(__dirname, "public")
));

app.use("/api/attendance", attendanceRoutes);

app.get("/", (req, res) => {
    res.send("Backend RFID Absensi Berjalan");
});

const PORT = process.env.PORT || 3000;

const server = http.createServer(app);

const io = new Server(server, {
    cors: {
        origin: "*"
    }
});

app.use((req, res, next) => {

    req.io = io;

    next();

});

server.listen(PORT, () => {

    console.log(
        `Server running on ${PORT}`
    );

});

app.get("/", (req, res) => {

    res.sendFile(
        path.join(__dirname, "public", "index.html")
    );

});
