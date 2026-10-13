package main

import (
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"strings"
	"time"

	"github.com/knadh/listmonk/models"
	"github.com/labstack/echo/v4"
	"github.com/labstack/echo/v4/middleware"
	"golang.org/x/time/rate"
)

const negroMatapacosListUUID = "f7a562f4-4162-4632-ad29-2cd6062c4f3a"
const negroMatapacosSignupPath = "/api/public/negromatapacos/subscription"

type negroMatapacosSignup struct {
	Email              string   `json:"email"`
	Name               string   `json:"name"`
	PreferredLanguages []string `json:"preferred_languages"`
	Consent            bool     `json:"consent"`
	Nonce              string   `json:"nonce"`
}

// Only this site's list and these two language values are writable publicly.
func decodeNegroMatapacosSignup(body io.Reader) (negroMatapacosSignup, error) {
	var req negroMatapacosSignup
	decoder := json.NewDecoder(body)
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&req); err != nil {
		return req, err
	}
	var extra any
	if err := decoder.Decode(&extra); err != io.EOF {
		return req, errors.New("expected one JSON object")
	}
	req.Email = strings.TrimSpace(req.Email)
	req.Name = strings.TrimSpace(req.Name)
	if !req.Consent || len(req.Email) == 0 || len(req.Email) > 254 || len([]rune(req.Name)) > 100 || len(req.PreferredLanguages) != 1 {
		return req, errors.New("invalid signup fields")
	}
	if lang := req.PreferredLanguages[0]; lang != "Spanish" && lang != "English" {
		return req, errors.New("invalid language")
	}
	return req, nil
}

type negroMatapacosSubscribers interface {
	GetList(int, string) (models.List, error)
	GetSubscriber(int, string, string) (models.Subscriber, error)
	InsertSubscriber(models.Subscriber, []int, []string, bool, bool) (models.Subscriber, bool, error)
	UpdateSubscriberWithLists(int, models.Subscriber, []int, []string, bool, bool, bool, []int, bool) (models.Subscriber, bool, error)
}

func saveNegroMatapacosSignup(core negroMatapacosSubscribers, req negroMatapacosSignup) (bool, error) {
	list, err := core.GetList(0, negroMatapacosListUUID)
	if err != nil || list.Type != models.ListTypePublic || list.Status != models.ListStatusActive {
		return false, echo.NewHTTPError(http.StatusServiceUnavailable, "Subscriptions unavailable")
	}
	attribs := models.JSON{
		"preferred_languages":    req.PreferredLanguages,
		"negromatapacos_consent": map[string]string{"at": time.Now().UTC().Format(time.RFC3339), "version": "2026-10-05", "source": "negromatapacos.cl", "scope": "launch, news, products and promotions"},
	}
	name := req.Name
	if name == "" {
		name = strings.Split(req.Email, "@")[0]
	}
	// Pass the concrete list ID so opt-in messages never include other lists.
	ids := []int{list.ID}
	_, hasOptin, err := core.InsertSubscriber(models.Subscriber{Name: name, Email: req.Email, Status: models.SubscriberStatusEnabled, Attribs: attribs}, ids, nil, false, true)
	if err == nil {
		return hasOptin, nil
	}
	var httpErr *echo.HTTPError
	if !errors.As(err, &httpErr) || httpErr.Code != http.StatusConflict {
		return false, err
	}
	sub, err := core.GetSubscriber(0, "", req.Email)
	if err != nil {
		return false, err
	}
	// Never reactivate disabled or blocklisted records or expose their status.
	if sub.Status != models.SubscriberStatusEnabled {
		return false, nil
	}
	if sub.Attribs == nil {
		sub.Attribs = models.JSON{}
	}
	for key, value := range attribs {
		sub.Attribs[key] = value
	}
	// Keep the existing name, status, attributes, and all other memberships.
	_, hasOptin, err = core.UpdateSubscriberWithLists(sub.ID, sub, ids, nil, false, false, true, nil, true)
	return hasOptin, err
}

func registerNegroMatapacosSignup(e *echo.Echo, handler echo.HandlerFunc) {
	origins := []string{"https://negromatapacos.cl", "https://gray-cliff-0a8287810.3.azurestaticapps.net"}
	g := e.Group(negroMatapacosSignupPath)
	g.Use(middleware.CORSWithConfig(middleware.CORSConfig{AllowOrigins: origins, AllowMethods: []string{http.MethodPost, http.MethodOptions}, AllowHeaders: []string{echo.HeaderContentType}, MaxAge: 600}))
	g.Use(func(next echo.HandlerFunc) echo.HandlerFunc {
		return func(c echo.Context) error {
			allowed := false
			for _, origin := range origins {
				if c.Request().Header.Get(echo.HeaderOrigin) == origin {
					allowed = true
					break
				}
			}
			if !allowed {
				return echo.NewHTTPError(http.StatusForbidden)
			}
			return next(c)
		}
	})
	g.Use(middleware.BodyLimit("4K"))
	// The existing Caddy proxy is the only public entry point. Use its last
	// forwarded address; an arbitrary client-supplied prefix cannot evade limits.
	g.Use(middleware.RateLimiterWithConfig(middleware.RateLimiterConfig{
		Store: middleware.NewRateLimiterMemoryStoreWithConfig(middleware.RateLimiterMemoryStoreConfig{Rate: rate.Limit(5.0 / 60), Burst: 5, ExpiresIn: 10 * time.Minute}),
		IdentifierExtractor: func(c echo.Context) (string, error) {
			forwarded := strings.Split(c.Request().Header.Get(echo.HeaderXForwardedFor), ",")
			if ip := strings.TrimSpace(forwarded[len(forwarded)-1]); ip != "" {
				return ip, nil
			}
			return c.RealIP(), nil
		},
	}))
	g.OPTIONS("", func(c echo.Context) error { return c.NoContent(http.StatusNoContent) })
	g.POST("", handler)
}
