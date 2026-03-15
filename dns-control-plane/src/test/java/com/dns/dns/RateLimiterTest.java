package com.dns;

import com.dns.dns.RateLimiter;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import static org.junit.jupiter.api.Assertions.*;



@DisplayName("RateLimiter")
class RateLimiterTest {

    private RateLimiter rateLimiter;

    private static final int MAX     = 5;
    private static final int WINDOW  = 2;

    @BeforeEach
    void setUp() {
        rateLimiter = new RateLimiter();
        ReflectionTestUtils.setField(rateLimiter, "maxQueries",    MAX);
        ReflectionTestUtils.setField(rateLimiter, "windowSeconds", WINDOW);
    }

    // ------------------------------------------------------------------
    // normal traffic
    // ------------------------------------------------------------------

    @Test
    @DisplayName("single request is never rate limited")
    void singleRequest_notLimited() {
        assertFalse(rateLimiter.isRateLimited("1.2.3.4"));
    }

    @Test
    @DisplayName("requests up to the limit are all allowed")
    void requestsUpToLimit_allAllowed() {
        for (int i = 0; i < MAX; i++) {
            assertFalse(rateLimiter.isRateLimited("1.2.3.4"),
                    "request " + (i + 1) + " should be allowed");
        }
    }

    // ------------------------------------------------------------------
    // rate limiting
    // ------------------------------------------------------------------

    @Test
    @DisplayName("request exactly at limit+1 is blocked")
    void requestAtLimitPlusOne_blocked() {
        for (int i = 0; i < MAX; i++) rateLimiter.isRateLimited("1.2.3.4");
        assertTrue(rateLimiter.isRateLimited("1.2.3.4"), "request at limit+1 should be blocked");
    }

    @Test
    @DisplayName("all subsequent requests after limit are blocked")
    void requestsAfterLimit_allBlocked() {
        for (int i = 0; i < MAX; i++) rateLimiter.isRateLimited("1.2.3.4");
        for (int i = 0; i < 10; i++) {
            assertTrue(rateLimiter.isRateLimited("1.2.3.4"),
                    "request " + (i + MAX + 1) + " should still be blocked");
        }
    }



    @Test
    @DisplayName("different IPs have independent counters")
    void differentIps_independentCounters() {
        for (int i = 0; i < MAX; i++) rateLimiter.isRateLimited("10.0.0.1");
        assertTrue(rateLimiter.isRateLimited("10.0.0.1"), "IP A should be limited");

        assertFalse(rateLimiter.isRateLimited("10.0.0.2"), "IP B should not be limited");
    }

    @Test
    @DisplayName("100 different IPs all pass their first request")
    void manyIps_allPassFirstRequest() {
        for (int i = 0; i < 100; i++) {
            assertFalse(rateLimiter.isRateLimited("10.0.0." + (i % 256)));
        }
    }

    // ------------------------------------------------------------------
    // sliding window expiry
    // ------------------------------------------------------------------

    @Test
    @DisplayName("requests allowed again after window expires")
    void windowExpiry_allowsNewRequests() throws InterruptedException {
        // Exhaust the limit
        for (int i = 0; i < MAX; i++) rateLimiter.isRateLimited("1.2.3.4");
        assertTrue(rateLimiter.isRateLimited("1.2.3.4"), "should be blocked before window expires");

        // Wait for window to expire
        Thread.sleep((WINDOW + 1) * 1000L);

        // Should be allowed again
        assertFalse(rateLimiter.isRateLimited("1.2.3.4"), "should be allowed after window expires");
    }

    // ------------------------------------------------------------------
    // reset
    // ------------------------------------------------------------------

    @Test
    @DisplayName("reset() clears rate limit state for all IPs")
    void reset_clearsAllState() {
        for (int i = 0; i < MAX; i++) rateLimiter.isRateLimited("1.2.3.4");
        assertTrue(rateLimiter.isRateLimited("1.2.3.4"), "should be blocked before reset");

        rateLimiter.reset();

        assertFalse(rateLimiter.isRateLimited("1.2.3.4"), "should be allowed after reset");
    }

    @Test
    @DisplayName("reset() clears state for multiple IPs simultaneously")
    void reset_clearsMultipleIps() {
        String[] ips = {"1.1.1.1", "2.2.2.2", "3.3.3.3"};
        for (String ip : ips) {
            for (int i = 0; i < MAX; i++) rateLimiter.isRateLimited(ip);
        }

        rateLimiter.reset();

        for (String ip : ips) {
            assertFalse(rateLimiter.isRateLimited(ip), ip + " should be allowed after reset");
        }
    }
}