package org.mfilm.sony;

/** One physical MENU press produces one action, even if the timer and key-up coincide. */
final class MenuPress {
    static final int HOLD_MS = 2000;
    enum Action { NONE, BACK, EXIT }
    private long started = -1;
    private boolean fired;

    boolean start(long time) {
        if (started >= 0) return false;
        started = time;
        fired = false;
        return true;
    }

    Action timer(long time) {
        if (started < 0 || fired || time - started < HOLD_MS) return Action.NONE;
        fired = true;
        return Action.EXIT;
    }

    Action release(long time, boolean canceled) {
        Action action = Action.NONE;
        if (started >= 0 && !canceled && !fired)
            action = time - started >= HOLD_MS ? Action.EXIT : Action.BACK;
        cancel();
        return action;
    }

    void cancel() { started = -1; fired = false; }
}
