import Capacitor
import WebKit

class MainViewController: CAPBridgeViewController {

    private weak var originalNavDelegate: WKNavigationDelegate?

    override func viewDidLoad() {
        super.viewDidLoad()
        if let wv = bridge?.webView {
            originalNavDelegate = wv.navigationDelegate
            wv.navigationDelegate = self
            wv.clipsToBounds = true
            wv.isOpaque = false
            wv.backgroundColor = .clear
            wv.scrollView.clipsToBounds = true
            wv.scrollView.bounces = false
            wv.scrollView.alwaysBounceHorizontal = false
            wv.scrollView.contentInsetAdjustmentBehavior = .never
        }
    }

    override var preferredStatusBarStyle: UIStatusBarStyle {
        traitCollection.userInterfaceStyle == .dark ? .lightContent : .darkContent
    }

    override func traitCollectionDidChange(_ previousTraitCollection: UITraitCollection?) {
        super.traitCollectionDidChange(previousTraitCollection)
        if previousTraitCollection?.userInterfaceStyle != traitCollection.userInterfaceStyle {
            setNeedsStatusBarAppearanceUpdate()
        }
    }
}

extension MainViewController: WKNavigationDelegate {

    // ── SSL bypass for self-signed certs ──────────────────────
    func webView(_ webView: WKWebView,
                 didReceive challenge: URLAuthenticationChallenge,
                 completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void) {
        if challenge.protectionSpace.authenticationMethod == NSURLAuthenticationMethodServerTrust,
           let trust = challenge.protectionSpace.serverTrust {
            completionHandler(.useCredential, URLCredential(trust: trust))
        } else {
            completionHandler(.performDefaultHandling, nil)
        }
    }

    // ── Forward everything else to Capacitor ──────────────────
    func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
        originalNavDelegate?.webView?(webView, didStartProvisionalNavigation: navigation)
    }
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        originalNavDelegate?.webView?(webView, didFinish: navigation)
    }
    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        originalNavDelegate?.webView?(webView, didFail: navigation, withError: error)
    }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        originalNavDelegate?.webView?(webView, didFailProvisionalNavigation: navigation, withError: error)
    }
    func webView(_ webView: WKWebView,
                 decidePolicyFor action: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        if let d = originalNavDelegate {
            d.webView?(webView, decidePolicyFor: action, decisionHandler: decisionHandler) ?? decisionHandler(.allow)
        } else { decisionHandler(.allow) }
    }
    func webView(_ webView: WKWebView,
                 decidePolicyFor response: WKNavigationResponse,
                 decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void) {
        if let d = originalNavDelegate {
            d.webView?(webView, decidePolicyFor: response, decisionHandler: decisionHandler) ?? decisionHandler(.allow)
        } else { decisionHandler(.allow) }
    }
}
