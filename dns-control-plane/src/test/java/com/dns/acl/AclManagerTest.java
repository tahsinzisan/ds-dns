package com.dns.acl;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import static org.junit.jupiter.api.Assertions.*;


class AclManagerTest {
    private AclManager aclManager = new AclManager();


    @Value("${dns.acl.subnet-prefix}")
    private String subNetPrefix;

    @Value("${dns.acl.octet3-min}")
    private int octet3Min;

    @Value("${dns.acl.octet3-max}")
    private int octet3Max;


    @Test
    @DisplayName("test out of subnet")
    void ipOutOfSubnet(){
        String ip = "192.167.0.0";
        assertFalse(aclManager.isInternalRequest(ip));
    }
    @Test
    @DisplayName("In subnet, but third octate out of range")
    void thirdOctateOutOfRange(){
        String ip  = "192.167.2.0";
        assertFalse(aclManager.isInternalRequest((ip)));
    }





    @Test
    @DisplayName("All address in subnet and third octate is inside the range")
    void validAddress(){
        String ip = "192.167.12.0";
        assertTrue(aclManager.isInternalRequest(ip));
    }

    @Test
    @DisplayName("Correct subnet, third octate less than minimum and then just the minimum")
    void variableThirdOctate(){
        String ip = "192.167.9.0";
        assertFalse(aclManager.isInternalRequest((ip)));

        ip = "192.167.10.0";
        assertTrue(aclManager.isInternalRequest(ip));

    }


    @Test
    @DisplayName("Correct subnet, Third octate is just the max then max+1")
    void variableThirdOctateMax(){
        String ip = "192.167.14.0";
        assertFalse(aclManager.isInternalRequest((ip)));

        ip = "192.167.13.0";
        assertTrue(aclManager.isInternalRequest(ip));

    }
}