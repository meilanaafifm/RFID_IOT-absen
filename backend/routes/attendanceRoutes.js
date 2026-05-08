const express = require("express");

const router = express.Router();

const Attendance = require("../models/Attendance");


// POST scan RFID
router.post("/scan", async (req, res) => {

    try {

        const attendance = await Attendance.create(req.body);

        res.status(201).json({
            success: true,
            data: attendance
        });

    } catch (error) {

        res.status(500).json({
            success: false,
            message: error.message
        });

    }

});


// GET semua data absensi
router.get("/", async (req, res) => {

    try {

        const data = await Attendance.find().sort({ waktu: -1 });

        res.json(data);

    } catch (error) {

        res.status(500).json({
            message: error.message
        });

    }

});

module.exports = router;