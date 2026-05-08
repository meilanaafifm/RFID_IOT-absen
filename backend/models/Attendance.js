const mongoose = require("mongoose");

const attendanceSchema = new mongoose.Schema({
    uid: {
        type: String,
        required: true
    },

    nama: {
        type: String,
        default: "Unknown"
    },

    waktu: {
        type: Date,
        default: Date.now
    }
});

module.exports = mongoose.model("Attendance", attendanceSchema);