package org.mfilm.sony;

/** A full press can expose once, while held, after the AF result for this press. */
final class ShutterFocus {
    enum State { IDLE, SEARCHING, LOCKED, MISSED, MANUAL, FIRED }

    interface Driver {
        void requestFocus(int attempt);
        void expose();
    }

    private final Driver driver;
    private int attempt;
    private boolean full;
    State state = State.IDLE;

    ShutterFocus(Driver driver) { this.driver = driver; }

    void halfDown(boolean manual) {
        if (state == State.IDLE) begin(manual);
    }

    void fullDown(boolean manual) {
        if (full) return;
        full = true;
        if (state == State.IDLE || state == State.MISSED || state == State.FIRED) {
            begin(manual);
        } else {
            exposeIfReady();
        }
    }

    private void begin(boolean manual) {
        ++attempt;
        if (manual) {
            state = State.MANUAL;
            exposeIfReady();
        } else {
            state = State.SEARCHING;
            driver.requestFocus(attempt);
        }
    }

    boolean finish(int request, boolean success) {
        if (request != attempt || state != State.SEARCHING) return false;
        state = success ? State.LOCKED : State.MISSED;
        exposeIfReady();
        return true;
    }

    private void exposeIfReady() {
        if (full && (state == State.LOCKED || state == State.MANUAL)) {
            state = State.FIRED;
            driver.expose();
        }
    }

    void fullUp() { full = false; }

    void reset() {
        ++attempt;
        full = false;
        state = State.IDLE;
    }
}
