export const CONNECT_NOTICES = {
  connected: "Connected to Strava. Start a sync to bring your activities in.",
  denied: "Strava access was not granted, so nothing was connected.",
  state: "That Strava response did not match a connection started here. Try again.",
  scope:
    "makerundev needs permission to read your activities, private ones included. Connect again and leave that box ticked.",
  failed: "Strava did not complete the connection. Check the client id and secret.",
};

export type ConnectNotice = keyof typeof CONNECT_NOTICES;
