# FurryTools - Installateur v1.4
# Lance FurryTools directement si tout est deja installe.
# Sinon : demande les droits admin puis affiche l'interface d'installation.

$PYTHON_URL      = "https://www.python.org/ftp/python/3.10.0/python-3.10.0-amd64.exe"
$STEAMTOOLS_URL  = "https://www.steamtools.net/res/st-setup-1.8.30.exe"
$SCRIPT_DIR      = Split-Path -Parent $MyInvocation.MyCommand.Path

# =============================================================================
# 1. VERIFICATION RAPIDE : si tout est OK, lancer directement (pas besoin d'admin)
# =============================================================================

function Find-PythonExe {
    $m = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $u = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$m;$u"
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) {
        $src = $cmd.Source
        if ($src -notlike "*WindowsApps*") {
            $null = & "$src" --version 2>&1
            if ($LASTEXITCODE -eq 0) { return $src }
        }
    }
    $fallbacks = @(
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python39\python.exe",
        "C:\Python310\python.exe",
        "$env:ProgramFiles\Python310\python.exe"
    )
    foreach ($p in $fallbacks) {
        if (Test-Path $p) {
            $null = & "$p" --version 2>&1
            if ($LASTEXITCODE -eq 0) { return $p }
        }
    }
    return $null
}

$quickPy = Find-PythonExe
if ($quickPy) {
    $null = & "$quickPy" -c "import PyQt5; import pypresence" 2>&1
    if ($LASTEXITCODE -eq 0) {
        $pyw    = $quickPy -replace "python\.exe$", "pythonw.exe"
        $exe    = if (Test-Path $pyw) { $pyw } else { $quickPy }
        $mainPy = Join-Path $SCRIPT_DIR "main.py"
        Start-Process $exe -ArgumentList "`"$mainPy`"" -WorkingDirectory $SCRIPT_DIR
        exit 0
    }
}

# =============================================================================
# 2. ELEVATION ADMINISTRATEUR
#    Python et SteamTools necessitent des droits admin pour s'installer.
#    Si on n'est pas admin, on relance le script avec elevation UAC.
# =============================================================================

$isAdmin = ([Security.Principal.WindowsPrincipal]`
    [Security.Principal.WindowsIdentity]::GetCurrent()`
).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    $self = if ($PSCommandPath) { $PSCommandPath } else { $MyInvocation.MyCommand.Path }
    try {
        Start-Process powershell `
            -Verb RunAs `
            -ArgumentList "-ExecutionPolicy Bypass -NoProfile -WindowStyle Hidden -File `"$self`""
    } catch {
        # L'utilisateur a refuse l'elevation : afficher quand meme l'interface
        # (l'installation pourra echouer mais au moins l'UI s'ouvre)
    }
    exit
}

# =============================================================================
# 3. INTERFACE GRAPHIQUE (on est administrateur)
# =============================================================================
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# --- Palette -----------------------------------------------------------------
$C_BG       = [System.Drawing.Color]::FromArgb( 22,  14,  40)
$C_ROW      = [System.Drawing.Color]::FromArgb( 40,  28,  72)
$C_ACCENT   = [System.Drawing.Color]::FromArgb(140,  70, 220)
$C_ACCENT_H = [System.Drawing.Color]::FromArgb(110,  55, 190)
$C_GREEN    = [System.Drawing.Color]::FromArgb( 40, 180,  85)
$C_GREEN_H  = [System.Drawing.Color]::FromArgb( 32, 145,  68)
$C_YELLOW   = [System.Drawing.Color]::FromArgb(220, 170,  30)
$C_RED      = [System.Drawing.Color]::FromArgb(210,  60,  60)
$C_WHITE    = [System.Drawing.Color]::FromArgb(225, 220, 235)
$C_DIM      = [System.Drawing.Color]::FromArgb( 95,  85, 120)
$C_TITLE    = [System.Drawing.Color]::FromArgb(195, 130, 255)
$C_SUB      = [System.Drawing.Color]::FromArgb(135, 118, 168)
$C_PENDING  = [System.Drawing.Color]::FromArgb( 68,  58,  95)
$C_SKIP     = [System.Drawing.Color]::FromArgb( 60,  55,  80)

# --- Fenetre -----------------------------------------------------------------
$form                 = New-Object System.Windows.Forms.Form
$form.Text            = "FurryTools - Installateur"
$form.ClientSize      = New-Object System.Drawing.Size(500, 535)
$form.MinimumSize     = New-Object System.Drawing.Size(500, 535)
$form.MaximumSize     = New-Object System.Drawing.Size(500, 535)
$form.StartPosition   = "CenterScreen"
$form.BackColor       = $C_BG
$form.ForeColor       = $C_WHITE
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox     = $false

# --- Badge admin (haut droite) -----------------------------------------------
$lblAdmin           = New-Object System.Windows.Forms.Label
$lblAdmin.Text      = "Administrateur"
$lblAdmin.Font      = New-Object System.Drawing.Font("Segoe UI", 7)
$lblAdmin.ForeColor = [System.Drawing.Color]::FromArgb(80, 200, 120)
$lblAdmin.BackColor = $C_BG
$lblAdmin.Location  = New-Object System.Drawing.Point(350, 4)
$lblAdmin.Size      = New-Object System.Drawing.Size(144, 14)
$lblAdmin.TextAlign = "MiddleRight"
$form.Controls.Add($lblAdmin)

# --- Logo --------------------------------------------------------------------
$logoPath = Join-Path $SCRIPT_DIR "logo.png"
$pnlTop   = New-Object System.Windows.Forms.Panel
$pnlTop.Location  = New-Object System.Drawing.Point(0, 0)
$pnlTop.Size      = New-Object System.Drawing.Size(500, 115)
$pnlTop.BackColor = $C_BG
$form.Controls.Add($pnlTop)

if (Test-Path $logoPath) {
    try {
        $img     = [System.Drawing.Image]::FromFile($logoPath)
        $picBox  = New-Object System.Windows.Forms.PictureBox
        $picBox.Image     = $img
        $picBox.SizeMode  = "Zoom"
        $picBox.Size      = New-Object System.Drawing.Size(90, 90)
        $picBox.Location  = New-Object System.Drawing.Point(205, 12)
        $picBox.BackColor = $C_BG
        $pnlTop.Controls.Add($picBox)
    } catch { $logoPath = "" }
}
if (-not (Test-Path $logoPath)) {
    $badge           = New-Object System.Windows.Forms.Label
    $badge.Text      = "FT"
    $badge.Font      = New-Object System.Drawing.Font("Segoe UI", 22, [System.Drawing.FontStyle]::Bold)
    $badge.ForeColor = [System.Drawing.Color]::White
    $badge.BackColor = $C_ACCENT
    $badge.Size      = New-Object System.Drawing.Size(72, 72)
    $badge.Location  = New-Object System.Drawing.Point(214, 20)
    $badge.TextAlign = "MiddleCenter"
    $pnlTop.Controls.Add($badge)
}

# --- Titre & sous-titre ------------------------------------------------------
$lblTitle           = New-Object System.Windows.Forms.Label
$lblTitle.Text      = "FurryTools"
$lblTitle.Font      = New-Object System.Drawing.Font("Segoe UI", 20, [System.Drawing.FontStyle]::Bold)
$lblTitle.ForeColor = $C_TITLE
$lblTitle.Location  = New-Object System.Drawing.Point(0, 118)
$lblTitle.Size      = New-Object System.Drawing.Size(500, 38)
$lblTitle.TextAlign = "MiddleCenter"
$form.Controls.Add($lblTitle)

$lblSub           = New-Object System.Windows.Forms.Label
$lblSub.Text      = "Installation automatique en un clic"
$lblSub.Font      = New-Object System.Drawing.Font("Segoe UI", 9)
$lblSub.ForeColor = $C_SUB
$lblSub.Location  = New-Object System.Drawing.Point(0, 158)
$lblSub.Size      = New-Object System.Drawing.Size(500, 20)
$lblSub.TextAlign = "MiddleCenter"
$form.Controls.Add($lblSub)

# --- Checkbox "Installation complete" ----------------------------------------
$chkSteam           = New-Object System.Windows.Forms.CheckBox
$chkSteam.Text      = "Installation complete - inclut SteamTools 1.8.30"
$chkSteam.Font      = New-Object System.Drawing.Font("Segoe UI", 9)
$chkSteam.ForeColor = $C_WHITE
$chkSteam.BackColor = $C_BG
$chkSteam.Location  = New-Object System.Drawing.Point(30, 186)
$chkSteam.Size      = New-Object System.Drawing.Size(440, 22)
$chkSteam.Checked   = $true
$form.Controls.Add($chkSteam)

# --- Etapes ------------------------------------------------------------------
function New-StepRow {
    param([int]$y, [string]$num, [string]$name)

    $row           = New-Object System.Windows.Forms.Panel
    $row.Location  = New-Object System.Drawing.Point(30, $y)
    $row.Size      = New-Object System.Drawing.Size(440, 44)
    $row.BackColor = $C_ROW
    $form.Controls.Add($row)

    $bar           = New-Object System.Windows.Forms.Panel
    $bar.Location  = New-Object System.Drawing.Point(0, 0)
    $bar.Size      = New-Object System.Drawing.Size(4, 44)
    $bar.BackColor = $C_PENDING
    $row.Controls.Add($bar)

    $numLbl           = New-Object System.Windows.Forms.Label
    $numLbl.Text      = $num
    $numLbl.Font      = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
    $numLbl.ForeColor = $C_DIM
    $numLbl.BackColor = $C_ROW
    $numLbl.Location  = New-Object System.Drawing.Point(12, 13)
    $numLbl.Size      = New-Object System.Drawing.Size(18, 18)
    $numLbl.TextAlign = "MiddleCenter"
    $row.Controls.Add($numLbl)

    $nameLbl           = New-Object System.Windows.Forms.Label
    $nameLbl.Text      = $name
    $nameLbl.Font      = New-Object System.Drawing.Font("Segoe UI", 9)
    $nameLbl.ForeColor = $C_WHITE
    $nameLbl.BackColor = $C_ROW
    $nameLbl.Location  = New-Object System.Drawing.Point(38, 13)
    $nameLbl.Size      = New-Object System.Drawing.Size(250, 18)
    $nameLbl.TextAlign = "MiddleLeft"
    $row.Controls.Add($nameLbl)

    $statusLbl           = New-Object System.Windows.Forms.Label
    $statusLbl.Text      = "En attente"
    $statusLbl.Font      = New-Object System.Drawing.Font("Segoe UI", 8)
    $statusLbl.ForeColor = $C_PENDING
    $statusLbl.BackColor = $C_ROW
    $statusLbl.Location  = New-Object System.Drawing.Point(295, 14)
    $statusLbl.Size      = New-Object System.Drawing.Size(138, 16)
    $statusLbl.TextAlign = "MiddleRight"
    $row.Controls.Add($statusLbl)

    return @{ Row = $row; Bar = $bar; Status = $statusLbl; Num = $numLbl; Name = $nameLbl }
}

$s1 = New-StepRow 218 "1" "Python 3.10"
$s2 = New-StepRow 269 "2" "Dependances Python (PyQt5...)"
$s3 = New-StepRow 320 "3" "SteamTools 1.8.30"

# --- Barre de progression ----------------------------------------------------
$pb          = New-Object System.Windows.Forms.ProgressBar
$pb.Location = New-Object System.Drawing.Point(30, 380)
$pb.Size     = New-Object System.Drawing.Size(440, 14)
$pb.Style    = "Continuous"
$pb.Minimum  = 0
$pb.Maximum  = 100
$pb.Value    = 0
$form.Controls.Add($pb)

$lblStatus           = New-Object System.Windows.Forms.Label
$lblStatus.Text      = "Cliquez sur le bouton pour commencer."
$lblStatus.Font      = New-Object System.Drawing.Font("Segoe UI", 8)
$lblStatus.ForeColor = $C_DIM
$lblStatus.Location  = New-Object System.Drawing.Point(30, 398)
$lblStatus.Size      = New-Object System.Drawing.Size(440, 18)
$form.Controls.Add($lblStatus)

# --- Boutons -----------------------------------------------------------------
function New-FlatBtn($txt, $x, $w, $bg, $bgh) {
    $b = New-Object System.Windows.Forms.Button
    $b.Text      = $txt
    $b.Location  = New-Object System.Drawing.Point($x, 430)
    $b.Size      = New-Object System.Drawing.Size($w, 44)
    $b.BackColor = $bg
    $b.ForeColor = [System.Drawing.Color]::White
    $b.FlatStyle = "Flat"
    $b.FlatAppearance.BorderSize         = 0
    $b.FlatAppearance.MouseOverBackColor = $bgh
    $b.Font      = New-Object System.Drawing.Font("Segoe UI", 10, [System.Drawing.FontStyle]::Bold)
    $b.Cursor    = [System.Windows.Forms.Cursors]::Hand
    $form.Controls.Add($b)
    return $b
}

$btnInstall = New-FlatBtn "Installer en 1 clic" 30  210 $C_ACCENT  $C_ACCENT_H
$btnLaunch  = New-FlatBtn "Lancer FurryTools"  260  210 $C_GREEN   $C_GREEN_H
$btnLaunch.Enabled = $false

# --- Pied de page ------------------------------------------------------------
$lblFooter           = New-Object System.Windows.Forms.Label
$lblFooter.Text      = "by rvmillions  -  discord.gg/Wx7wP9fmUf"
$lblFooter.Font      = New-Object System.Drawing.Font("Segoe UI", 7)
$lblFooter.ForeColor = [System.Drawing.Color]::FromArgb(65, 58, 90)
$lblFooter.Location  = New-Object System.Drawing.Point(0, 508)
$lblFooter.Size      = New-Object System.Drawing.Size(500, 18)
$lblFooter.TextAlign = "MiddleCenter"
$form.Controls.Add($lblFooter)

# =============================================================================
# ANIMATIONS
# =============================================================================
$script:targetPct  = 0
$script:animPhase  = $false
$script:activeStep = $null

$progTimer          = New-Object System.Windows.Forms.Timer
$progTimer.Interval = 16
$progTimer.Add_Tick({
    if ($pb.Value -lt $script:targetPct) {
        $pb.Value = [Math]::Min($pb.Value + 1, $script:targetPct)
    }
})
$progTimer.Start()

$pulseTimer          = New-Object System.Windows.Forms.Timer
$pulseTimer.Interval = 500
$pulseTimer.Add_Tick({
    if ($script:activeStep -ne $null) {
        $script:animPhase = -not $script:animPhase
        $clr = if ($script:animPhase) {
            [System.Drawing.Color]::FromArgb(255, 195, 40)
        } else { $C_YELLOW }
        $script:activeStep.Bar.BackColor    = $clr
        $script:activeStep.Status.ForeColor = $clr
    }
})
$pulseTimer.Start()

# =============================================================================
# FONCTIONS UTILITAIRES
# =============================================================================
function SetStatus {
    param([string]$msg, [int]$pct = -1)
    $lblStatus.Text = $msg
    if ($pct -ge 0) { $script:targetPct = $pct }
    [System.Windows.Forms.Application]::DoEvents()
}

function Set-Step {
    param($step, [string]$state)
    switch ($state) {
        "active"  {
            $script:activeStep            = $step
            $step.Bar.BackColor           = $C_YELLOW
            $step.Status.Text             = "En cours..."
            $step.Status.ForeColor        = $C_YELLOW
            $step.Num.ForeColor           = $C_YELLOW
        }
        "done"    {
            if ($script:activeStep -eq $step) { $script:activeStep = $null }
            $step.Bar.BackColor           = $C_GREEN
            $step.Status.Text             = "OK"
            $step.Status.ForeColor        = $C_GREEN
            $step.Num.ForeColor           = $C_GREEN
        }
        "error"   {
            if ($script:activeStep -eq $step) { $script:activeStep = $null }
            $step.Bar.BackColor           = $C_RED
            $step.Status.Text             = "Erreur"
            $step.Status.ForeColor        = $C_RED
            $step.Num.ForeColor           = $C_RED
        }
        "skipped" {
            if ($script:activeStep -eq $step) { $script:activeStep = $null }
            $step.Bar.BackColor           = $C_SKIP
            $step.Status.Text             = "Ignore"
            $step.Status.ForeColor        = $C_DIM
            $step.Num.ForeColor           = $C_DIM
        }
        "pending" {
            $step.Bar.BackColor           = $C_PENDING
            $step.Status.Text             = "En attente"
            $step.Status.ForeColor        = $C_PENDING
            $step.Num.ForeColor           = $C_DIM
        }
    }
    [System.Windows.Forms.Application]::DoEvents()
}

# =============================================================================
# ETAPE 1 : Python
# =============================================================================
function Step-Python {
    Set-Step $s1 "active"
    SetStatus "Recherche de Python sur ce PC..." 4

    $py = Find-PythonExe
    if ($py) {
        $ver = (& "$py" --version 2>&1).ToString().Trim()
        Set-Step $s1 "done"
        SetStatus "Python trouve : $ver" 30
        return $py
    }

    SetStatus "Telechargement de Python 3.10.0 (environ 28 Mo)..." 6
    $pb.Style = "Marquee"; $pb.MarqueeAnimationSpeed = 20
    [System.Windows.Forms.Application]::DoEvents()

    $installer = "$env:TEMP\python-3.10.0-amd64.exe"
    try {
        (New-Object System.Net.WebClient).DownloadFile($PYTHON_URL, $installer)
    } catch {
        $pb.Style = "Continuous"; $pb.Value = 0
        Set-Step $s1 "error"
        SetStatus "Echec du telechargement de Python." -1
        [System.Windows.Forms.MessageBox]::Show(
            "Impossible de telecharger Python 3.10.`n`nErreur : $_`n`n" +
            "Installez Python manuellement :`nhttps://www.python.org/downloads/release/python-3100/",
            "Erreur", "OK", "Error") | Out-Null
        return $null
    }

    $pb.Style = "Continuous"
    SetStatus "Installation de Python 3.10.0 (1-2 minutes)..." 18

    $proc = Start-Process -FilePath $installer `
        -ArgumentList "/quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_launcher=1" `
        -Wait -PassThru
    Remove-Item $installer -Force -ErrorAction SilentlyContinue

    if ($proc.ExitCode -ne 0) {
        Set-Step $s1 "error"
        SetStatus "L'installation de Python a echoue." -1
        [System.Windows.Forms.MessageBox]::Show(
            "L'installation de Python a echoue (code $($proc.ExitCode)).",
            "Erreur", "OK", "Error") | Out-Null
        return $null
    }

    $py = Find-PythonExe
    if (-not $py) {
        Set-Step $s1 "error"
        SetStatus "Python installe mais introuvable. Relancez ce programme." -1
        [System.Windows.Forms.MessageBox]::Show(
            "Python a ete installe mais n'est pas detecte.`nFermez et relancez l'installateur.",
            "Erreur", "OK", "Warning") | Out-Null
        return $null
    }

    $ver = (& "$py" --version 2>&1).ToString().Trim()
    Set-Step $s1 "done"
    SetStatus "$ver installe." 30
    return $py
}

# =============================================================================
# ETAPE 2 : Dependances pip
# =============================================================================
function Step-Deps {
    param([string]$py)
    Set-Step $s2 "active"
    SetStatus "Mise a jour de pip..." 35

    $null = & "$py" -m pip install --upgrade pip 2>&1

    SetStatus "Installation de PyQt5 et pypresence..." 52
    $req      = Join-Path $SCRIPT_DIR "requirements.txt"
    $depOut   = & "$py" -m pip install -r "$req" 2>&1
    $exitCode = $LASTEXITCODE

    if ($exitCode -eq 0) {
        Set-Step $s2 "done"
        SetStatus "Dependances installees." 70
        return $true
    } else {
        Set-Step $s2 "error"
        $errLines = ($depOut | Where-Object { $_ -match "(?i)error" }) -join "`n"
        SetStatus "Echec lors de l'installation des dependances." -1
        [System.Windows.Forms.MessageBox]::Show(
            "L'installation des dependances a echoue.`n`n$errLines",
            "Erreur", "OK", "Error") | Out-Null
        return $false
    }
}

# =============================================================================
# ETAPE 3 : SteamTools
# =============================================================================
function Step-SteamTools {
    Set-Step $s3 "active"
    SetStatus "Telechargement de SteamTools 1.8.30 (environ 20 Mo)..." 74

    $pb.Style = "Marquee"; $pb.MarqueeAnimationSpeed = 20
    [System.Windows.Forms.Application]::DoEvents()

    $installer = "$env:TEMP\st-setup-1.8.30.exe"
    try {
        (New-Object System.Net.WebClient).DownloadFile($STEAMTOOLS_URL, $installer)
    } catch {
        $pb.Style = "Continuous"; $pb.Value = 70
        Set-Step $s3 "error"
        SetStatus "Echec du telechargement de SteamTools." -1
        [System.Windows.Forms.MessageBox]::Show(
            "Impossible de telecharger SteamTools.`n`nErreur : $_",
            "Erreur", "OK", "Error") | Out-Null
        return $false
    }

    $pb.Style = "Continuous"
    SetStatus "Lancement de l'installateur SteamTools - suivez les etapes..." 80
    [System.Windows.Forms.Application]::DoEvents()

    # L'installateur SteamTools est interactif : l'utilisateur suit le wizard
    $proc = Start-Process -FilePath $installer -Wait -PassThru
    Remove-Item $installer -Force -ErrorAction SilentlyContinue

    if ($proc.ExitCode -eq 0 -or $proc.ExitCode -eq 3010) {
        # 3010 = succes avec redemarrage requis
        Set-Step $s3 "done"
        SetStatus "SteamTools installe avec succes." 95
        return $true
    } else {
        # L'utilisateur a peut-etre annule ou il y a eu une erreur
        Set-Step $s3 "skipped"
        SetStatus "SteamTools : installation annulee ou ignoree." 90
        return $true   # on ne bloque pas le lancement de FurryTools
    }
}

# =============================================================================
# REACTION AU CHANGEMENT DE LA CHECKBOX
# =============================================================================
$chkSteam.Add_CheckedChanged({
    if ($chkSteam.Checked) {
        $s3.Name.Text         = "SteamTools 1.8.30"
        $s3.Name.ForeColor    = $C_WHITE
        $s3.Status.Text       = "En attente"
        $s3.Status.ForeColor  = $C_PENDING
        $s3.Bar.BackColor     = $C_PENDING
        $s3.Num.ForeColor     = $C_DIM
    } else {
        $s3.Name.Text         = "SteamTools  (non selectionne)"
        $s3.Name.ForeColor    = $C_DIM
        $s3.Status.Text       = "Ignore"
        $s3.Status.ForeColor  = $C_DIM
        $s3.Bar.BackColor     = $C_SKIP
        $s3.Num.ForeColor     = $C_DIM
    }
    [System.Windows.Forms.Application]::DoEvents()
})

# =============================================================================
# BOUTON "Installer en 1 clic"
# =============================================================================
$btnInstall.Add_Click({
    $btnInstall.Enabled = $false
    $btnLaunch.Enabled  = $false
    Set-Step $s1 "pending"
    Set-Step $s2 "pending"
    if ($chkSteam.Checked) { Set-Step $s3 "pending" } else { Set-Step $s3 "skipped" }
    $pb.Value         = 0
    $script:targetPct = 0

    # Etape 1 : Python
    $py = Step-Python
    if (-not $py) { $btnInstall.Enabled = $true; return }

    # Etape 2 : dependances
    $ok = Step-Deps $py
    if (-not $ok) { $btnInstall.Enabled = $true; return }

    # Etape 3 : SteamTools (optionnel)
    if ($chkSteam.Checked) {
        Step-SteamTools | Out-Null
    }

    # Succes
    $script:targetPct  = 100
    SetStatus "Installation terminee. Cliquez sur 'Lancer FurryTools'." 100
    $btnLaunch.Enabled  = $true
    $btnInstall.Enabled = $true
    $btnInstall.Text    = "Reinstaller"
})

# =============================================================================
# BOUTON "Lancer FurryTools"
# =============================================================================
$btnLaunch.Add_Click({
    $py = Find-PythonExe
    if (-not $py) {
        [System.Windows.Forms.MessageBox]::Show(
            "Python introuvable. Cliquez d'abord sur 'Installer en 1 clic'.",
            "Erreur", "OK", "Error") | Out-Null
        return
    }
    $pyw    = $py -replace "python\.exe$", "pythonw.exe"
    $exe    = if (Test-Path $pyw) { $pyw } else { $py }
    $mainPy = Join-Path $SCRIPT_DIR "main.py"
    Start-Process $exe -ArgumentList "`"$mainPy`"" -WorkingDirectory $SCRIPT_DIR
    Start-Sleep -Milliseconds 1000
    $progTimer.Stop(); $pulseTimer.Stop()
    $form.Close()
})

# =============================================================================
# VERIFICATION INITIALE AU DEMARRAGE
# =============================================================================
$form.Add_Shown({
    # Initialiser l'etat visuel de s3 selon la checkbox
    $chkSteam.Checked = $true   # force le CheckedChanged initial
    $chkSteam.Checked = $true

    $py = Find-PythonExe
    if ($py) {
        $ver = (& "$py" --version 2>&1).ToString().Trim()
        $s1.Status.Text      = $ver
        $s1.Status.ForeColor = $C_SUB
        $s1.Bar.BackColor    = $C_ACCENT
        SetStatus "Python trouve. Cliquez sur 'Installer en 1 clic' pour continuer." 0
    } else {
        SetStatus "Python sera telecharge automatiquement. Connexion internet requise." 0
    }
})

[System.Windows.Forms.Application]::Run($form)
