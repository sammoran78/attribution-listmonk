package main

import (
	"github.com/labstack/echo/v4"
	"net/http"
	"strings"
)

func (a *App) NegroMatapacosSubscription(c echo.Context) error {
	c.Response().Header().Set("Cache-Control", "no-store")
	if !a.cfg.EnablePublicSubPage {
		return echo.NewHTTPError(http.StatusServiceUnavailable, "Subscriptions unavailable")
	}
	if !strings.HasPrefix(strings.ToLower(c.Request().Header.Get(echo.HeaderContentType)), echo.MIMEApplicationJSON) {
		return echo.NewHTTPError(http.StatusUnsupportedMediaType)
	}
	req, err := decodeNegroMatapacosSignup(c.Request().Body)
	if err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "Invalid signup fields")
	}
	if req.Nonce != "" {
		return c.JSON(http.StatusOK, map[string]any{"data": map[string]bool{"accepted": true, "has_optin": false}})
	}
	req.Email, err = a.importer.SanitizeEmail(req.Email)
	if err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "Invalid email address")
	}
	hasOptin, err := saveNegroMatapacosSignup(a.core, req)
	if err != nil {
		// Do not return subscriber details or database errors to this public client.
		return echo.NewHTTPError(http.StatusServiceUnavailable, "Subscriptions unavailable")
	}
	return c.JSON(http.StatusOK, map[string]any{"data": map[string]bool{"accepted": true, "has_optin": hasOptin}})
}
