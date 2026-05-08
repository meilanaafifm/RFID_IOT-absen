const express = require("express");
const jwt = require("jsonwebtoken");

const router = express.Router();

router.post("/login", async (req, res) => {

    const { username, password } = req.body;

    if (
        username === "admin" &&
        password === "kelompokiot"
    ) {

        const token = jwt.sign(
            { username, role: "admin" },
            "SECRET_KEY",
            { expiresIn: "1d" }
        );

        return res.json({
            success: true,
            token,
            role: "admin"
        });

    }

    res.status(401).json({
        success: false,
        message: "Login gagal"
    });

});

module.exports = router;
