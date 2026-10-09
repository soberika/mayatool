// mcd. Cloth State 0.1 - stage 0 test script for the state cloth layer.
// Put it into the worn dress (or the test ribbons) together with the
// overlay animations. It never touches the wearer's AO: it only starts and
// stops animations named below, which key cloth bones only.
//
// Inventory names (missing ones fall back to "cloth_stand", then to none):
//   cloth_stand  cloth_walk  cloth_run  cloth_sit  cloth_ground
// Test animation (command "test"): the first animation whose name starts
// with "mcd_test".
//
// Chat commands on channel 7 (owner only):
//   /7 on | off      enable or disable the cloth layer
//   /7 debug         toggle timing log (state change -> overlay started)
//   /7 test          start/stop toggling the test animation every 4 s
//   /7 rate 0.2      polling interval in seconds (0.05 - 1.0)
//   /7 status        print current state and overlay
//
// NOT YET VERIFIED IN SECOND LIFE.

integer CHANNEL = 7;
float gRate = 0.2;
integer gEnabled = TRUE;
integer gDebug = TRUE;
integer gTesting = FALSE;
integer gTestOn = FALSE;
float gTestNext = 0.0;
integer gListen;

string gState = "";
string gOverlay = "";
string gTestAnim = "";

// llGetAnimation() reports the default animation state, not the AO's
// animation, so this works with any AO.
string coarseState(string sl)
{
    if (sl == "Walking" || sl == "Striding" || sl == "CrouchWalking") return "walk";
    if (sl == "Running") return "run";
    if (sl == "Sitting") return "sit";
    if (sl == "Sitting on Ground" || sl == "Crouching") return "ground";
    return "stand";
}

string overlayFor(string st)
{
    string name = "cloth_" + st;
    if (llGetInventoryType(name) == INVENTORY_ANIMATION) return name;
    if (llGetInventoryType("cloth_stand") == INVENTORY_ANIMATION) return "cloth_stand";
    return "";
}

integer hasPermission()
{
    return (llGetPermissions() & PERMISSION_TRIGGER_ANIMATION)
        && llGetPermissionsKey() == llGetOwner();
}

play(string name)
{
    if (!hasPermission() || name == gOverlay) return;
    if (gOverlay != "") llStopAnimation(gOverlay);
    if (name != "") llStartAnimation(name);
    gOverlay = name;
}

stopAll()
{
    if (hasPermission())
    {
        if (gOverlay != "") llStopAnimation(gOverlay);
        if (gTestAnim != "" && gTestOn) llStopAnimation(gTestAnim);
    }
    gOverlay = "";
    gTestOn = FALSE;
}

findTestAnim()
{
    gTestAnim = "";
    integer count = llGetInventoryNumber(INVENTORY_ANIMATION);
    integer i;
    for (i = 0; i < count && gTestAnim == ""; ++i)
    {
        string name = llGetInventoryName(INVENTORY_ANIMATION, i);
        if (llSubStringIndex(name, "mcd_test") == 0) gTestAnim = name;
    }
}

poll()
{
    float now = llGetTime();
    if (gTesting && gTestAnim != "" && now >= gTestNext && hasPermission())
    {
        gTestOn = !gTestOn;
        if (gTestOn) llStartAnimation(gTestAnim);
        else llStopAnimation(gTestAnim);
        if (gDebug) llOwnerSay("[" + (string)now + "] Test " + gTestAnim
            + " an=" + (string)gTestOn);
        gTestNext = now + 4.0;
    }
    if (!gEnabled) return;
    string sl = llGetAnimation(llGetOwner());
    string current = coarseState(sl);
    if (current == gState) return;
    string previous = gState;
    gState = current;
    play(overlayFor(current));
    if (gDebug) llOwnerSay("[" + (string)now + "] " + previous + " -> " + current
        + " (" + sl + "), Overlay: " + gOverlay);
}

init()
{
    llListenRemove(gListen);
    gListen = llListen(CHANNEL, "", llGetOwner(), "");
    gState = "";
    gOverlay = "";
    findTestAnim();
    if (llGetAttached())
        llRequestPermissions(llGetOwner(), PERMISSION_TRIGGER_ANIMATION);
    else
        llOwnerSay("mcd. Cloth State: bitte tragen, nicht rezzen.");
}

default
{
    state_entry()
    {
        llResetTime();
        init();
    }

    on_rez(integer param)
    {
        init();
    }

    attach(key id)
    {
        if (id == NULL_KEY)
        {
            stopAll();
            llSetTimerEvent(0.0);
        }
    }

    changed(integer change)
    {
        if (change & CHANGED_OWNER) llResetScript();
        if (change & CHANGED_INVENTORY)
        {
            findTestAnim();
            gState = "";
        }
    }

    run_time_permissions(integer perms)
    {
        if (perms & PERMISSION_TRIGGER_ANIMATION)
        {
            llOwnerSay("mcd. Cloth State bereit. Befehle: /" + (string)CHANNEL
                + " on|off|debug|test|rate <s>|status");
            llSetTimerEvent(gRate);
        }
    }

    timer()
    {
        poll();
    }

    listen(integer channel, string name, key id, string message)
    {
        list words = llParseString2List(llToLower(llStringTrim(message, STRING_TRIM)),
            [" "], []);
        string command = llList2String(words, 0);
        if (command == "on")
        {
            gEnabled = TRUE;
            gState = "";
        }
        else if (command == "off")
        {
            gEnabled = FALSE;
            play("");
            gState = "";
        }
        else if (command == "debug")
        {
            gDebug = !gDebug;
            llOwnerSay("Debug " + (string)gDebug);
        }
        else if (command == "test")
        {
            if (gTestAnim == "")
            {
                llOwnerSay("Keine Animation, deren Name mit mcd_test beginnt.");
                return;
            }
            gTesting = !gTesting;
            if (!gTesting && gTestOn)
            {
                llStopAnimation(gTestAnim);
                gTestOn = FALSE;
            }
            gTestNext = llGetTime();
            llOwnerSay("Test " + (string)gTesting + ": " + gTestAnim);
        }
        else if (command == "rate")
        {
            float rate = (float)llList2String(words, 1);
            if (rate < 0.05) rate = 0.05;
            if (rate > 1.0) rate = 1.0;
            gRate = rate;
            llSetTimerEvent(gRate);
            llOwnerSay("Abfrage alle " + (string)gRate + " s");
        }
        else if (command == "status")
        {
            llOwnerSay("Zustand " + gState + ", Overlay " + gOverlay
                + ", aktiv " + (string)gEnabled + ", Test " + (string)gTesting);
        }
    }
}
